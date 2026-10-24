"""Production service (phase 1): wire persistent Cases to the repo's engine.

Nothing here re-implements underwriting: parse/extract/derive/completeness/
evaluate/rank/narrative/decide/settle all come straight from the demo backend
(ui.app.run_pipeline / ui.app.decide), which itself wraps nodes/*. Phase 1 only
adds persistence around them.
"""
import base64
import json
import os
import uuid
import urllib.error as _urllib

from . import docstore, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Reuse the demo backend's engine wiring (importable module, guarded main).
import ui.app as demo  # noqa: E402


def _clean_filename(name: str) -> str:
    return (name or "file").replace(" ", "_")


# --- case creation ----------------------------------------------------------

def create_case(broker_firm: str, underwriter: str, sample_case_id: str | None,
                documents: list[dict] | None) -> dict:
    """Create a Case from a pinned sample or uploaded documents (base64 JSON)."""
    if documents:
        docs = []
        for d in documents:
            raw = base64.b64decode(d.get("content_b64", ""))
            docs.append({"doc_id": _clean_filename(d.get("filename", "doc")),
                         "filename": d.get("filename", "doc"),
                         "content_bytes": raw})
        source = "upload"
    else:
        sample_case_id = sample_case_id or "20-demo-accept-full"
        path = os.path.join(ROOT, "docs", "data", "samples", "cases",
                            f"{sample_case_id}.json")
        if not os.path.exists(path):
            raise ValueError(f"unknown sample case {sample_case_id}")
        raw = json.load(open(path, encoding="utf-8"))
        docs = raw["documents"]  # pre-parsed, carry structured_hint
        source = "sample"

    case_id = "C-" + uuid.uuid4().hex[:10]
    with store.new_session() as s:
        c = store.Case(case_id=case_id,
                       submission_reference="PROD-" + case_id[2:],
                       broker_firm=(broker_firm or "").strip(),
                       underwriter=(underwriter or "").strip(),
                       status="new", source=source, created_at=store.now())
        s.add(c)
        s.commit()
    # Documents live on disk under data/cases/<case_id>/ from intake onward
    # (phase 2): the case survives server restarts, and the provenance viewer
    # opens the very bytes that were received.
    docstore.save_docs(case_id, docs)
    return {"case_id": case_id}


# --- evaluation -------------------------------------------------------------

def evaluate_case(case_id: str, llm: str | None = None) -> dict:
    """Run the full pipeline on a Case and persist an append-only Evaluation."""
    with store.new_session() as s:
        case = s.get(store.Case, case_id)
        if case is None:
            raise LookupError("case not found")
        docs = docstore.load_run_docs(case_id)
        try:
            state = demo.run_pipeline([dict(d) for d in docs],
                                      case.submission_reference, llm=llm)
        except (RuntimeError, _urllib.URLError) as e:
            # Missing/invalid extractor credentials or provider failure: a
            # clean 400, never a 500 — the evaluation simply did not run.
            raise ValueError(f"extractor unavailable: {e}")
        if "halt" in state and state.get("halt") == "parse":
            outcome, reco = "halt", None
        else:
            reco = state.get("recommendation")
            if reco and not str(reco).startswith("no eligible"):
                outcome = reco
            else:
                outcome = "no-eligible"
        # Phase 5: attach third-party reference facts to the payload (frozen into
        # the append-only evaluation). Data, never a decision - provenance carried.
        try:
            from . import reference as ref_mod
            ref_mod.attach(state)
        except Exception:
            state["reference_facts"] = []
        # Phase 6: overlay live ledger capacity figures onto the snapshot.
        try:
            from . import capacity_desk as cd_mod
            cd_mod.augment_payload(state)
        except Exception:
            pass
        ev = store.Evaluation(case_id=case_id, created_at=store.now(), llm=llm,
                              model=((state.get("model_versions") or {})
                                     .get("extraction", "")),
                              outcome=outcome, recommendation=reco,
                              payload=state)
        s.add(ev)
        # A decided case that gains fresh info stays decided until re-decided;
        # otherwise the newest evaluation makes the case assessed.
        if case.status != "decided":
            case.status = "assessed"
        case.assessed_at = store.now()
        s.commit()
        return {"evaluation_id": ev.evaluation_id, "outcome": outcome}


# --- decision ---------------------------------------------------------------

def decide_case(case_id: str, action: str, underwriter: str,
                selected_binder: str | None = None,
                reason_code: str | None = None) -> dict:
    """Record the human decision on the latest evaluation; persist both."""
    with store.new_session() as s:
        case = s.get(store.Case, case_id)
        if case is None:
            raise LookupError("case not found")
        ev = (s.query(store.Evaluation)
               .filter(store.Evaluation.case_id == case_id)
               .order_by(store.Evaluation.evaluation_id.desc()).first())
        if ev is None:
            raise ValueError("run an evaluation first")
        run_state = dict(ev.payload)
        human = {"action": action, "underwriter_id": underwriter,
                 "selected_binder": selected_binder, "reason_code": reason_code}
        out = demo.decide(run_state, human)
        decision = out.get("decision") or {}
        if not decision.get("valid"):
            return {"valid": False, "error": decision.get("error", "invalid")}
        settlement = out.get("settlement") or {}
        d = store.Decision(case_id=case_id, evaluation_id=ev.evaluation_id,
                           created_at=store.now(), underwriter=underwriter,
                           action=action,
                           selected_binder=decision.get("selected_binder"),
                           reason_code=reason_code,
                           outcome=settlement.get("action", "none"),
                           detail={"settlement": settlement,
                                   "audit_id": out.get("audit_id")})
        # refer_back opens `awaiting-broker` and auto-issues a Request round
        # from the engine-named gaps (Q7/Q2) — the letter then carries the
        # ask list (Q10). Bound decisions get their letter the same way.
        letter_input = {"action": action, "selected_binder":
                        decision.get("selected_binder"), "underwriter_id": underwriter}
        letter, round_issued = None, False
        if action == "refer_back":
            if open_round(case_id) is None:
                try:
                    rnd = create_round(s, case, ev.payload, [], {}, underwriter)
                    round_issued = True
                    rnd_meta = {"number": rnd.number,
                                "due": rnd.due_at.strftime("%Y-%m-%d")}
                    items_pub = [{"question": it.question}
                                 for it in s.query(store.RequestItem)
                                 .filter(store.RequestItem.round_id == rnd.round_id,
                                         store.RequestItem.suppressed.is_(False))
                                 .order_by(store.RequestItem.item_id).all()]
                    letter = build_letter(case, letter_input, ev.payload,
                                          items_pub, rnd_meta)
                    case.status = "awaiting-broker"
                except ValueError:  # no engine-named gaps to ask
                    letter = build_letter(case, letter_input, ev.payload, None, None)
            else:
                letter = build_letter(case, letter_input, ev.payload, None, None)
        else:
            letter = build_letter(case, letter_input, ev.payload, None, None)
        d.detail["letter"] = letter
        s.add(d)
        case.underwriter = underwriter
        case.decided_at = store.now()
        # A refer_back with an open round leaves the case awaiting-broker
        # (Q7); every other decision closes it as decided (bound = terminal).
        case.status = "awaiting-broker" if (action == "refer_back" and round_issued) \
            else "decided"
        s.commit()
        # Phase 6: capacity alerts fire at the moment a reservation lands.
        try:
            settlement_binder = (settlement.get("binder") if isinstance(settlement, dict)
                                 else None)
            if settlement.get("action") == "reserved" and settlement_binder:
                from . import capacity_desk as cd_mod
                cd_mod.check_alerts(settlement_binder, placed_by=underwriter)
        except Exception:
            pass
        # Broker notification: bound letters say what was placed; referred
        # letters carry the ask list (Q10, Q13).
        from . import mail
        mail.send(mail.broker_recipient(case.broker_firm),
                  f"{case.submission_reference} — outcome: {letter['title']}",
                  letter["body"])
        return {"valid": True, "outcome_letters": _outcome_word(action),
                "settlement": settlement, "audit_id": out.get("audit_id"),
                "letter": letter}


def _outcome_word(action: str) -> str:
    return {"accept": "bound", "override": "bound (override)",
            "refer_back": "referred back"}.get(action, action)


# --- reads ------------------------------------------------------------------

def list_cases() -> list[dict]:
    with store.new_session() as s:
        cases = s.query(store.Case).order_by(store.Case.created_at.desc()).all()
        out = []
        for c in cases:
            ev = (s.query(store.Evaluation)
                   .filter(store.Evaluation.case_id == c.case_id)
                   .order_by(store.Evaluation.evaluation_id.desc()).first())
            latest = None
            if ev is not None:
                latest = {"outcome": ev.outcome, "llm": ev.llm,
                          "recommendation": ev.recommendation}
            rnd = (s.query(store.RequestRound)
                   .filter(store.RequestRound.case_id == c.case_id,
                           store.RequestRound.status == "open").first())
            out.append({"case_id": c.case_id,
                        "submission_reference": c.submission_reference,
                        "broker_firm": c.broker_firm, "underwriter": c.underwriter,
                        "status": c.status, "source": c.source,
                        "created_at": c.created_at.isoformat(sep=" ", timespec="minutes"),
                        "sla": store.sla_state(c), "latest": latest,
                        "round": ({"number": rnd.number,
                                   "sla": store.round_sla_state(rnd),
                                   "due": rnd.due_at.strftime("%Y-%m-%d")}
                                  if rnd else None)})
        return out


def case_detail(case_id: str) -> dict | None:
    with store.new_session() as s:
        c = s.get(store.Case, case_id)
        if c is None:
            return None
        evals = (s.query(store.Evaluation)
                  .filter(store.Evaluation.case_id == case_id)
                  .order_by(store.Evaluation.evaluation_id.desc()).all())
        decisions = (s.query(store.Decision)
                      .filter(store.Decision.case_id == case_id)
                      .order_by(store.Decision.decision_id.desc()).all())
        return {"case": c, "evaluations": evals, "decisions": decisions}


# --- provenance viewer (phase 2) --------------------------------------------

import html as _html
import re as _re


def _flex_find(text: str, quote: str) -> tuple[int, int] | None:
    """Find a quote in text tolerating case + whitespace differences."""
    if not text or not quote:
        return None
    parts = [_re.escape(p) for p in quote.split()]
    if not parts:
        return None
    pat = r"\s+".join(parts)
    m = _re.search(pat, text, _re.IGNORECASE)
    if m:
        return m.start(), m.end()
    return None


def _hl(s: str) -> str:
    return _html.escape(s)


def all_doc_views(case_id: str) -> list[dict]:
    """Every document viewer for a case (multi-doc provenance, v1.15+)."""
    detail = case_detail(case_id)
    if detail is None:
        return []
    payload = detail["evaluations"][0].payload if detail["evaluations"] else {}
    ids = [d.get("doc_id") for d in (payload.get("documents") or []) if d.get("doc_id")]
    if not ids:
        ids = list(docstore.manifest_text(case_id).keys())
    out = []
    for did in ids:
        v = doc_view(case_id, did)
        if v is not None:
            out.append(v)
    return out
    """One document + every fact the latest evaluation took from it.

    Highlights are computed over stored text (display only, never stored):
    live extractors carry a quote in source_locator; the stub extractor's
    structured_hint locator is rendered as the machine-readable record with
    the fact's field value marked. Nothing is inferred here — no text, no
    truth, just the mapping back to the document.
    """
    detail = case_detail(case_id)
    if detail is None:
        return None
    evals = detail["evaluations"]
    latest = evals[0] if evals else None
    payload = latest.payload if latest else {}
    docs = {d.get("doc_id"): d for d in (payload.get("documents") or [])}
    doc = docs.get(doc_id)
    text = (doc or {}).get("text") or ""
    meta = payload.get("extracted_meta") or {}
    todos = [(f, m) for f, m in meta.items()
             if m.get("source_document_id") == doc_id and m.get("present")]

    marks: list[dict] = []   # highlights inside the document text
    recs: list[dict] = []    # highlights inside the structured record
    for field, m in todos:
        locator = (m.get("source_locator") or "").strip()
        if locator == "structured_hint" or not locator:
            recs.append({"field": field, "value": _hl(json.dumps(m.get("value")))})
            continue
        span = _flex_find(text, locator)
        if span:
            marks.append({"field": field, "start": span[0], "end": span[1],
                          "quote": locator})
        else:
            marks.append({"field": field, "start": None, "end": None,
                          "quote": locator})  # quote not located — shown as-is

    # Render text with non-overlapping marks (first match wins, engine-facts stay plain).
    marks_text = [m for m in marks if m["start"] is not None]
    marks_text.sort(key=lambda x: x["start"])
    out, pos = [], 0
    for m in marks_text:
        if m["start"] < pos:
            continue
        out.append(_hl(text[pos:m["start"]]))
        out.append(f'<mark data-f="{_hl(m["field"])}" title="{_hl(m["field"])}">')
        out.append(_hl(text[m["start"]:m["end"]]))
        out.append("</mark>")
        pos = m["end"]
    out.append(_hl(text[pos:]))
    text_html = "".join(out)

    # Structured record: deterministic pretty-print of the exact hint the stub
    # reads, with one <mark> per fact this evaluation took from it.
    hint = (doc or {}).get("structured_hint")
    rec_html = None
    if hint is not None:
        take = {r["field"]: m.get("value") for r in recs for m in [meta[r["field"]]]}
        lines = ["{"]
        keys = list(hint.keys())
        for i, k in enumerate(keys):
            inline = _hl(json.dumps(hint[k], default=str))
            comma = "," if i < len(keys) - 1 else ""
            if k in take:
                lines.append(f'  <mark data-f="{_hl(k)}" title="{_hl(k)}">"{_hl(k)}": {inline}{comma}</mark>')
            else:
                lines.append(f'  "{_hl(k)}": {inline}{comma}')
        lines.append("}")
        rec_html = "\n".join(lines)

    return {"case": detail["case"], "doc_id": doc_id,
            "doc": doc or {}, "evaluation_id": latest.evaluation_id if latest else None,
            "text_html": text_html, "has_text": bool(text),
            "has_structured": hint is not None, "structured_html": rec_html,
            "found": [m for m in marks if m["start"] is not None],
            "missing": [m for m in marks if m["start"] is None],
            "structured_facts": recs}


# --- phase 3: Request rounds, letters, delta, portal -------------------------
#
# Settled decisions this section implements (phase-3 grill, ADR 0001):
# - One active Request round per Case (Q2); issued from engine gaps only (Q4).
# - Broker answers: typed portal text AND/OR documents, marked per item (Q3, Q15);
#   typed answers enter the engine as a machine-readable answer sheet the broker
#   portal produced — data from the broker, provenance-marked, never invented.
# - Submission locks the round and runs the successor evaluation synchronously
#   (Q14); the Case never forks (Q1), refer_back opens `awaiting-broker` (Q7).
# - Letters: bound names the selected binder; referred letters carry the ask
#   list; brokers never see other binders, scores, rules or lineage (Q10).
# - Round SLA is 10 business days, visual breach signage only (Q11).
# - Notifications: round issued -> broker; broker answered -> staff (Q13).
# - Any underwriter may act on any case (Q12); no per-case assignment v1.

DEFAULT_EVAL_LLM = os.environ.get("APP_DEFAULT_LLM", "") or None  # stub if unset


def _staff_emails():
    from . import mail as mail_mod
    return mail_mod.staff_recipients()


def correct_case(case_id: str, corrections: dict, underwriter: str) -> dict:
    """Apply underwriter corrections to the latest evaluation's extracted facts,
    then re-run the engine (derive → completeness → evaluate → rank →
    summarize) and append a successor Evaluation. The correction trail
    (pre-value, who, when) is preserved in the metadata.

    Corrections is {field: new_value}. Only fields present in the latest
    evaluation's extracted_meta are accepted; unknown fields are ignored.
    """
    with store.new_session() as s:
        case = s.get(store.Case, case_id)
        if case is None:
            raise LookupError("case not found")
        ev = (s.query(store.Evaluation)
               .filter(store.Evaluation.case_id == case_id)
               .order_by(store.Evaluation.evaluation_id.desc()).first())
        if ev is None:
            raise ValueError("run an evaluation first")
        payload = dict(ev.payload)
        # Only accept corrections for known fields.
        meta = payload.get("extracted_meta") or {}
        valid = {k: v for k, v in corrections.items() if k in meta}
        if not valid:
            raise ValueError("no valid fields to correct")
        # Apply corrections via the engine's correction module.
        import nodes.correct as corr_mod
        corrected = corr_mod.apply(payload, valid, underwriter)
        payload["extracted"] = corrected["extracted"]
        payload["extracted_meta"] = corrected["extracted_meta"]
        # Re-run the engine from derive onward (no re-extraction, no re-parse).
        try:
            payload.update(demo.drv.derive(payload))
            payload.update(demo.comp.check(payload))
            if not (payload.get("completeness") or {}).get("can_evaluate", True):
                # Completeness now fails after correction — keep the halt.
                pass
            else:
                payload.update(demo.mb.evaluate_binders(payload))
                payload.update(demo.mb.rank(payload))
                payload.update(demo.nar.summarize(payload))
                payload["halt"] = None
        except Exception as e:
            raise ValueError(f"re-evaluation failed: {e}")
        if "halt" not in payload:
            payload["halt"] = None
        # Determine outcome.
        if payload.get("halt") == "parse":
            outcome, reco = "halt", None
        elif payload.get("halt") == "completeness":
            outcome, reco = "halt", None
        else:
            reco = payload.get("recommendation")
            if reco and not str(reco).startswith("no eligible"):
                outcome = reco
            else:
                outcome = "no-eligible"
        # Phase 5: re-attach reference facts (they may have changed if
        # territory was corrected).
        try:
            from . import reference as ref_mod
            ref_mod.attach(payload)
        except Exception:
            payload["reference_facts"] = payload.get("reference_facts", [])
        # Phase 6: overlay live capacity figures.
        try:
            from . import capacity_desk as cd_mod
            cd_mod.augment_payload(payload)
        except Exception:
            pass
        new_ev = store.Evaluation(case_id=case_id, created_at=store.now(),
                                  llm=ev.llm, model=ev.model,
                                  outcome=outcome, recommendation=reco,
                                  payload=payload)
        s.add(new_ev)
        if case.status != "decided":
            case.status = "assessed"
        case.assessed_at = store.now()
        s.commit()
        return {"evaluation_id": new_ev.evaluation_id, "outcome": outcome,
                "corrected_fields": list(valid.keys())}
    from . import mail
    return mail.staff_recipients()


def open_round(case_id: str):
    with store.new_session() as s:
        return (s.query(store.RequestRound)
                .filter(store.RequestRound.case_id == case_id,
                        store.RequestRound.status == "open").first())


def rounds_for_case(case_id: str) -> list[dict]:
    with store.new_session() as s:
        rows = (s.query(store.RequestRound)
                .filter(store.RequestRound.case_id == case_id)
                .order_by(store.RequestRound.number.desc()).all())
        ids = [r.round_id for r in rows]
        items = (s.query(store.RequestItem)
                 .filter(store.RequestItem.round_id.in_(ids or [0])).all()
                 if ids else [])
        by_round: dict[int, list] = {}
        for it in sorted(items, key=lambda x: x.item_id):
            by_round.setdefault(it.round_id, []).append(it)
        out = []
        for r in rows:
            out.append({"round": r, "items": by_round.get(r.round_id, []),
                        "sla": store.round_sla_state(r)})
        return out


def latest_gaps(case_id: str) -> list[dict]:
    """Named engine gaps from the freshest evaluation (the only source of ask
    items — the engine names them, humans never invent requests)."""
    with store.new_session() as s:
        ev = (s.query(store.Evaluation)
              .filter(store.Evaluation.case_id == case_id)
              .order_by(store.Evaluation.evaluation_id.desc()).first())
    if ev is None or ev.payload.get("halt") == "parse":
        return []
    from . import gaps as gaps_mod
    return gaps_mod.cannot_assess(ev.payload)


def create_round(s, case, payload: dict, selected_fields: list[str],
                 notes: dict[str, str], issued_by: str) -> store.RequestRound:
    """Create the round + items on the given session (shared by the manual
    issue route and the refer_back auto-issue; commit belongs to the caller)."""
    from . import gaps as gaps_mod
    all_gaps = gaps_mod.cannot_assess(payload or {})
    chosen = [g for g in all_gaps if g["field"] in (selected_fields or
                                                    [g["field"] for g in all_gaps])]
    if not chosen:
        raise ValueError("no engine-named gaps to issue (nothing to ask)")
    number = (s.query(store.RequestRound)
              .filter(store.RequestRound.case_id == case.case_id).count() + 1)
    rnd = store.RequestRound(case_id=case.case_id, number=number, status="open",
                             issued_at=store.now(),
                             due_at=store._bd_deadline(store.now(), store.SLA_ROUND_DAYS),
                             issued_by=issued_by,
                             items=[{"field": g["field"], "question": g["question"],
                                     "raised_by": g["raised_by"]} for g in chosen])
    s.add(rnd)
    s.flush()
    selected = selected_fields if selected_fields else [g["field"] for g in chosen]
    for g in chosen:
        s.add(store.RequestItem(round_id=rnd.round_id, field=g["field"],
                                question=g["question"], raised_by=g["raised_by"],
                                suppressed=g["field"] not in selected,
                                note=(notes or {}).get(g["field"], "")))
    # autoflush=False: push the pending items now so same-session queries
    # (e.g. the letter's ask-list snapshot) see them.
    s.flush()
    return rnd


def issue_round(case_id: str, selected_fields: list[str], notes: dict[str, str],
                issued_by: str) -> dict:
    """The underwriter issues one round from engine-named gaps (Q4)."""
    with store.new_session() as s:
        case = s.get(store.Case, case_id)
        if case is None:
            raise LookupError("case not found")
        if open_round(case_id) is not None:
            raise ValueError("an active Request round already exists on this case")
        ev = (s.query(store.Evaluation)
              .filter(store.Evaluation.case_id == case_id)
              .order_by(store.Evaluation.evaluation_id.desc()).first())
        if ev is None:
            raise ValueError("run an evaluation first")
        rnd = create_round(s, case, ev.payload, selected_fields, notes, issued_by)
        case.status = "awaiting-broker"
        s.commit()
        n, due = rnd.number, rnd.due_at
        ref, firm = case.submission_reference, case.broker_firm
        public = (len(selected_fields) if selected_fields
                  else len(rnd.items or []))
    # Round-issued notification to the broker (Q13) — after commit.
    from . import mail
    body = (f"Information request round {n} was issued on case {ref} ({firm}).\n"
            f"Due: {due:%Y-%m-%d} (10 business days).\n\n")
    for r in rounds_for_case(case_id):
        if r["round"].round_id == rnd.round_id:
            for it in r["items"]:
                if not it.suppressed:
                    body += f"- {it.question}\n"
    mail.send(mail.broker_recipient(firm),
              f"{ref} — information request round {n}", body)
    return {"round_id": rnd.round_id, "number": n, "items_sent": public}


def save_draft(case_id: str, round_id: int, answers: dict[int, tuple[str, str]]) -> dict:
    """Broker draft edit (Q15): typed text + optional doc marking, until lock."""
    with store.new_session() as s:
        r = s.get(store.RequestRound, round_id)
        if r is None or r.case_id != case_id or r.status != "open":
            raise ValueError("round is not open for drafting")
        for it in (s.query(store.RequestItem)
                   .filter(store.RequestItem.round_id == round_id,
                           store.RequestItem.suppressed.is_(False)).all()):
            if it.item_id in answers:
                text, doc_id = answers[it.item_id]
                it.answer_text = text
                it.answer_doc_id = doc_id or None
        s.commit()
    return {"saved": True}


def _answer_sheet(case, rnd, items: list) -> dict:
    """Build the broker's machine-readable answer sheet document.

    It is a document like any other (provenance marks it source=portal round
    N): a text sheet for humans and live extractors, plus a structured record
    the keyless stub can read — its content is exactly the broker's typed
    answers and doc markings, never the engine's inventions.
    """
    hint: dict = {}
    lines = [f"Broker answer sheet — round {rnd.number} — case "
             f"{case.submission_reference} — firm {case.broker_firm}"]
    for it in items:
        if it.suppressed:
            continue
        val = (it.answer_text or "").strip()
        doc = it.answer_doc_id
        if not val and not doc:
            continue
        if val and (it.field not in hint) and _flat(it.field):
            from . import gaps as gaps_mod
            hint[it.field] = gaps_mod.coerce(it.field, val)
        shown = val if val else f"[answer provided in document: {doc}]"
        lines.append(f"{it.field}: {shown}")
    return {"doc_id": f"round-{rnd.number}-answers",
            "filename": f"round-{rnd.number}-answers.txt",
            "text": "\n".join(lines), "structured_hint": hint}


def _flat(field: str) -> bool:
    return "." not in (field or "")


def attach_broker_docs(case_id: str, uploads: list[tuple[str, bytes]]) -> list[str]:
    """Store documents a broker attached (draft or submit) under the case."""
    doc_ids: list[str] = []
    for filename, data in (uploads or []):
        fname = os.path.basename(filename or "upload.bin")
        doc_ids.extend(docstore.add_docs(
            case_id, [{"doc_id": fname, "filename": fname,
                       "content_bytes": data}]))
    return doc_ids


def submit_round(case_id: str, round_id: int,
                 uploads: list[tuple[str, bytes]] | None = None) -> dict:
    """Lock the round (Q15), file the broker's documents, run the successor
    evaluation synchronously on the same Case (Q14, ADR 0001), notify staff."""
    with store.new_session() as s:
        r = s.get(store.RequestRound, round_id)
        if r is None or r.case_id != case_id or r.status != "open":
            raise ValueError("round is not open for submission")
        case = s.get(store.Case, case_id)
        items = (s.query(store.RequestItem)
                 .filter(store.RequestItem.round_id == round_id)
                 .order_by(store.RequestItem.item_id).all())
        r.status = "locked"
        r.submitted_at = store.now()
        s.commit()

    # Broker documents -> disk (append to the manifest; nothing overwritten).
    doc_ids = attach_broker_docs(case_id, uploads)

    # Answer sheet document joins the case's document set for the re-run.
    with store.new_session() as s:
        case = s.get(store.Case, case_id)
        rnd = s.get(store.RequestRound, round_id)
        items = (s.query(store.RequestItem)
                 .filter(store.RequestItem.round_id == round_id)
                 .order_by(store.RequestItem.item_id).all())
        sheet = _answer_sheet(case, rnd, items)
        docstore.add_docs(case_id, [sheet])
        s.commit()

    # Successor evaluation — synchronous (Q14). Append-only; the Case is
    # unchanged institutionally (a new evaluation is chained, ADR 0001).
    out = evaluate_case(case_id, llm=DEFAULT_EVAL_LLM)
    with store.new_session() as s:
        r = s.get(store.RequestRound, round_id)
        r.answered_evaluation_id = out.get("evaluation_id")
        s.commit()
    # Staff notification (Q13).
    from . import mail
    mail.send(", ".join(_staff_emails()),
              f"{case.submission_reference} — broker answered round {rnd.number}",
              f"Round {rnd.number} on case {case.submission_reference} "
              f"({case.broker_firm}) was submitted and re-evaluated: "
              f"evaluation #{out.get('evaluation_id')} ({out.get('outcome')}).\n"
              f"Answer sheet: {sheet['doc_id']}; broker documents: "
              f"{', '.join(doc_ids) or 'none'}.\n"
              f"Open the case to review and decide.")
    out.update({"round_locked": True, "uploaded_doc_ids": doc_ids,
                "answer_sheet": sheet["doc_id"]})
    return out


# --- letters (Q10) -----------------------------------------------------------

LETTER_TERMS_FIELDS = ("total_insured_value", "coverage_type",
                       "valuation_basis", "requested_inception_date")


def build_letter(case, decision, payload: dict, round_items: list[dict] | None,
                 round_meta: dict | None) -> dict:
    """Deterministic letter text at decision time; stored on the Decision."""
    action = decision.get("action")
    binder = decision.get("selected_binder")
    facts = payload.get("extracted") or {}
    terms = "\n".join(f"- {f}: {facts.get(f)}" for f in LETTER_TERMS_FIELDS
                      if facts.get(f) is not None)
    if action in ("accept", "override"):
        kind, title = "bound", f"Bound with {binder}"
        body = (f"Dear {case.broker_firm},\n\n"
                f"Case {case.submission_reference} is bound with {binder} "
                f"by {decision.get('underwriter_id')}.\n")
        if terms:
            body += f"\nKey details on the record:\n{terms}\n"
        body += ("\nThis letter is the engine view that crosses to you; "
                 "placements, scores and internal rules are not shared.\n")
    else:  # refer_back
        kind, title = "referred", "Referred back for information"
        body = (f"Dear {case.broker_firm},\n\n"
                f"Case {case.submission_reference} could not be placed on the "
                f"information provided.\n")
        if round_items:
            body += (f"Request round {round_meta.get('number')} was issued "
                     f"(due {round_meta.get('due')} — 10 business days):\n\n")
            for i, it in enumerate(round_items, 1):
                body += f"{i}. {it['question']}\n"
        else:
            body += "No binder is eligible on the provided data; nothing was invented.\n"
    return {"kind": kind, "title": title, "body": body,
            "created_at": store.now().isoformat(sep=" ", timespec="seconds")}


# --- delta view (Q9) ----------------------------------------------------------

def delta_view(prev_payload: dict, curr_payload: dict) -> dict:
    """What changed between two successive evaluations: facts, per-binder
    outcomes, rule flips, recommendation. Unchanged things are not listed."""
    fp, fc = prev_payload.get("extracted") or {}, curr_payload.get("extracted") or {}
    mp, mc = prev_payload.get("extracted_meta") or {}, curr_payload.get("extracted_meta") or {}
    facts = []
    for f in sorted(set(fp) | set(fc)):
        if fp.get(f) != fc.get(f):
            facts.append({"field": f, "prev": fp.get(f), "curr": fc.get(f),
                          "conf": (mc.get(f) or {}).get("confidence")})
    bprev = {b.get("binder_id"): b for b in (prev_payload.get("binder_results") or [])}
    bcurr = {b.get("binder_id"): b for b in (curr_payload.get("binder_results") or [])}
    binders = []
    for bid in sorted(set(bprev) | set(bcurr)):
        po, co = (bprev.get(bid) or {}).get("outcome"), (bcurr.get(bid) or {}).get("outcome")
        flips = []
        rp = {o.get("rule_id"): o.get("outcome")
              for o in (bprev.get(bid) or {}).get("rule_outcomes") or []}
        rc = {o.get("rule_id"): o.get("outcome")
              for o in (bcurr.get(bid) or {}).get("rule_outcomes") or []}
        for rid in sorted(set(rp) | set(rc)):
            if rp.get(rid) != rc.get(rid):
                flips.append({"rule_id": rid, "prev": rp.get(rid), "curr": rc.get(rid)})
        if po != co or flips:
            binders.append({"binder_id": bid, "prev": po, "curr": co, "flips": flips})
    prev_reco = prev_payload.get("recommendation")
    curr_reco = curr_payload.get("recommendation")
    sprev = (prev_payload.get("scores") or {}).get(prev_reco) if prev_reco else None
    scurr = (curr_payload.get("scores") or {}).get(curr_reco) if curr_reco else None
    return {"facts": facts, "binders": binders,
            "reco": {"prev": prev_reco, "prev_score": sprev,
                     "curr": curr_reco, "curr_score": scurr}}


# --- portal reads -------------------------------------------------------------

def check_breach_notices() -> int:
    """Answer-SLA breaches get signage everywhere (Q11) and ONE staff email
    per round (Q13) — the notice flag makes the email idempotent."""
    from . import mail as mail_mod
    with store.new_session() as s:
        rows = (s.query(store.RequestRound)
                .filter(store.RequestRound.status == "open",
                        store.RequestRound.breach_notified_at.is_(None)).all())
        n = 0
        for r in rows:
            if store.round_sla_state(r) != "breached":
                continue
            case = s.get(store.Case, r.case_id)
            mail_mod.send(", ".join(_staff_emails()),
                          f"{case.submission_reference} — round {r.number} breached",
                          f"Request round {r.number} on case {case.submission_reference} "
                          f"({case.broker_firm}) passed its 10-business-day clock and "
                          f"the broker has not answered.\n"
                          f"(Signage only — no auto-escalation in this release.)")
            r.breach_notified_at = store.now()
            n += 1
        s.commit()
    return n


def portal_cases(user) -> list[dict]:
    with store.new_session() as s:
        cases = (s.query(store.Case)
                 .filter(store.Case.broker_firm == (getattr(user, "broker_firm", "")))
                 .order_by(store.Case.created_at.desc()).all())
        out = []
        for c in cases:
            rnd = open_round(c.case_id)
            out.append({"case_id": c.case_id, "reference": c.submission_reference,
                        "status": c.status, "created": c.created_at,
                        "open_round": (rnd.number if rnd else None),
                        "open_round_due": (rnd.due_at if rnd else None)})
        return out


def portal_case(user, case_id: str):
    """Broker view of one case: rounds (no suppressed items), letters, the
    broker's own documents. Never evaluation lineage, scores or other binders."""
    with store.new_session() as s:
        c = s.get(store.Case, case_id)
        if c is None or c.broker_firm != getattr(user, "broker_firm", ""):
            return None
        decs = (s.query(store.Decision)
                .filter(store.Decision.case_id == case_id)
                .order_by(store.Decision.decision_id.desc()).all())
        letters = [{"decision_id": d.decision_id, "created": d.created_at,
                    **((d.detail or {}).get("letter") or {})}
                   for d in decs if ((d.detail or {}).get("letter"))]
        rounds = []
        for r in (s.query(store.RequestRound)
                  .filter(store.RequestRound.case_id == case_id)
                  .order_by(store.RequestRound.number.desc()).all()):
            items = (s.query(store.RequestItem)
                     .filter(store.RequestItem.round_id == r.round_id,
                             store.RequestItem.suppressed.is_(False))
                     .order_by(store.RequestItem.item_id).all())
            rounds.append({"round": r, "items": items, "sla": store.round_sla_state(r)})
        return {"case": {"case_id": c.case_id, "reference": c.submission_reference,
                         "broker_firm": c.broker_firm, "status": c.status,
                         "created_at": c.created_at},
                "rounds": rounds, "letters": letters,
                "documents": sorted(v["doc_id"] for v in
                                    docstore.manifest_text(case_id).values())}


def doc_view(case_id: str, doc_id: str) -> dict | None:
    """One document + every fact the latest evaluation took from it.

    Multi-source aware: a fact is shown if this doc is its source_document_id
    OR appears in its `sources` list (phase: multi-doc provenance).
    """
    detail = case_detail(case_id)
    if detail is None:
        return None
    evals = detail["evaluations"]
    latest = evals[0] if evals else None
    payload = latest.payload if latest else {}
    docs = {d.get("doc_id"): d for d in (payload.get("documents") or [])}
    doc = docs.get(doc_id)
    text = (doc or {}).get("text") or ""
    meta = payload.get("extracted_meta") or {}
    todos = []
    for f, m in meta.items():
        if not m.get("present"):
            continue
        sid = m.get("source_document_id")
        srcs = [s.get("source_document_id") for s in (m.get("sources") or [])]
        if doc_id == sid or doc_id in srcs:
            todos.append((f, m))

    marks: list[dict] = []
    recs: list[dict] = []
    for field, m in todos:
        locator = (m.get("source_locator") or "").strip()
        if locator == "structured_hint" or not locator:
            recs.append({"field": field, "value": _hl(json.dumps(m.get("value")))})
            continue
        span = _flex_find(text, locator)
        if span:
            marks.append({"field": field, "start": span[0], "end": span[1],
                          "quote": locator})
        else:
            marks.append({"field": field, "start": None, "end": None,
                          "quote": locator})

    marks_text = [m for m in marks if m["start"] is not None]
    marks_text.sort(key=lambda x: x["start"])
    out, pos = [], 0
    for m in marks_text:
        if m["start"] < pos:
            continue
        out.append(_hl(text[pos:m["start"]]))
        out.append(f'<mark data-f="{_hl(m["field"])}" title="{_hl(m["field"])}">')
        out.append(_hl(text[m["start"]:m["end"]]))
        out.append("</mark>")
        pos = m["end"]
    out.append(_hl(text[pos:]))
    text_html = "".join(out)

    hint = (doc or {}).get("structured_hint")
    rec_html = None
    if hint is not None:
        take = {r["field"]: m.get("value") for r in recs for m in [meta[r["field"]]]}
        lines = ["{"]
        keys = list(hint.keys())
        for i, k in enumerate(keys):
            inline = _hl(json.dumps(hint[k], default=str))
            comma = "," if i < len(keys) - 1 else ""
            if k in take:
                lines.append(f'  <mark data-f="{_hl(k)}" title="{_hl(k)}">"{_hl(k)}": {inline}{comma}</mark>')
            else:
                lines.append(f'  "{_hl(k)}": {inline}{comma}')
        lines.append("}")
        rec_html = "\n".join(lines)

    return {"case": detail["case"], "doc_id": doc_id,
            "doc": doc or {}, "evaluation_id": latest.evaluation_id if latest else None,
            "text_html": text_html, "has_text": bool(text),
            "has_structured": hint is not None, "structured_html": rec_html,
            "found": [m for m in marks if m["start"] is not None],
            "missing": [m for m in marks if m["start"] is None],
            "structured_facts": recs}


def all_doc_views(case_id: str) -> list[dict]:
    """Every document viewer for a case (multi-doc provenance)."""
    detail = case_detail(case_id)
    if detail is None:
        return []
    payload = detail["evaluations"][0].payload if detail["evaluations"] else {}
    ids = [d.get("doc_id") for d in (payload.get("documents") or []) if d.get("doc_id")]
    if not ids:
        ids = list(docstore.manifest_text(case_id).keys())
    out = []
    for did in ids:
        v = doc_view(case_id, did)
        if v is not None:
            out.append(v)
    return out
