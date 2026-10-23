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

from . import store

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
    # Documents are stored in-memory only for this phase 1; the evaluation
    # persists the full run state, so nothing is needed on disk between runs.
    _CASE_DOCS[case_id] = docs
    return {"case_id": case_id}


# Document payloads live only long enough to run an evaluation; the persisted
# Evaluation payload is the durable record (phase 2 moves docs into storage).
_CASE_DOCS: dict[str, list[dict]] = {}


# --- evaluation -------------------------------------------------------------

def evaluate_case(case_id: str, llm: str | None = None) -> dict:
    """Run the full pipeline on a Case and persist an append-only Evaluation."""
    with store.new_session() as s:
        case = s.get(store.Case, case_id)
        if case is None:
            raise LookupError("case not found")
        docs = _CASE_DOCS.get(case_id)
        if docs is None:
            raise ValueError("documents no longer in memory — recreate the case "
                             "(phase 1 keeps uploaded documents in memory only)")
        state = demo.run_pipeline([dict(d) for d in docs],
                                  case.submission_reference, llm=llm)
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
