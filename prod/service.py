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
        s.add(d)
        case.status = "decided"
        case.underwriter = underwriter
        case.decided_at = store.now()
        s.commit()
        return {"valid": True, "outcome_letters": _outcome_word(action),
                "settlement": settlement, "audit_id": out.get("audit_id")}


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
            out.append({"case_id": c.case_id,
                        "submission_reference": c.submission_reference,
                        "broker_firm": c.broker_firm, "underwriter": c.underwriter,
                        "status": c.status, "source": c.source,
                        "created_at": c.created_at.isoformat(sep=" ", timespec="minutes"),
                        "sla": store.sla_state(c), "latest": latest})
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


def doc_view(case_id: str, doc_id: str) -> dict | None:
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
