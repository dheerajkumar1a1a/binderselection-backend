"""Durable persistence: checkpointer + append-only audit (BFR-NFR-019, BFR-AUD)."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def get_checkpointer():
    """Context manager: use as `with get_checkpointer() as cp: build(cp)`."""
    conn = os.environ.get("BINDER_PG_CONN")
    if conn:
        from langgraph.checkpoint.postgres import PostgresSaver
        return PostgresSaver.from_conn_string(conn)
    from langgraph.checkpoint.sqlite import SqliteSaver
    return SqliteSaver.from_conn_string(str(BASE / ".checkpoints.sqlite"))


def write_audit(state: dict) -> dict:
    audit_dir = BASE / "audit"
    audit_dir.mkdir(exist_ok=True)
    record = {
        "evaluation_id": f"eval-{uuid.uuid4().hex[:8]}",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "submission_reference": state.get("submission_reference"),
        "documents": [{k: v for k, v in (d or {}).items()
                       if k not in ("content_bytes", "content_b64")}
                      for d in state.get("documents") or []],
        "parse": state.get("parse"),
        "extracted": state.get("extracted"),
        "extracted_meta": state.get("extracted_meta"),
        "capacity_snapshot": state.get("capacity_snapshot"),
        "rule_outcomes": state.get("rule_outcomes"),
        "binder_outcome": state.get("binder_outcome"),
        "binder_results": state.get("binder_results"),
        "scores": state.get("scores"),
        "recommendation": state.get("recommendation"),
        "decision": state.get("decision"),
        "settlement": state.get("settlement"),
        "narrative": state.get("narrative"),
        "stage_timings": state.get("stage_timings"),
        "model_versions": state.get("model_versions"),
        "supersedes": state.get("supersedes"),
    }
    with open(audit_dir / "decisions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"audit_id": record["evaluation_id"]}


def evidence_pack(record: dict) -> str:
    """Single human-readable evidence pack for one evaluation (BFR-AUD-008)."""
    lines = [f"# Evidence pack — {record.get('evaluation_id')}",
             f"Submission: {record.get('submission_reference')} · evaluated {record.get('evaluated_at')}"]
    if record.get("supersedes"):
        lines.append(f"Supersedes: {record['supersedes']} (original left intact, BFR-AUD-004)")
    lines.append("## Documents (parse status per document)")
    for d in record.get("documents") or []:
        lines.append(f"- {d.get('doc_id')}: {d.get('filename')} -> "
                     f"{d.get('parse_status', '?')}{(': ' + d['failure_reason']) if d.get('failure_reason') else ''}")
    lines.append("## Extracted values (value | confidence | source)")
    for f, m in (record.get("extracted_meta") or {}).items():
        if isinstance(m, dict):
            lines.append(f"- {f}: {m.get('value')} | conf {m.get('confidence')} | {m.get('source_document_id')}")
            if m.get("corrected_by"):
                lines.append(f"  corrected by {m['corrected_by']} at {m.get('corrected_at')}, was {m.get('pre_correction_value')}")
    lines.append("## Binder outcomes")
    for r in record.get("binder_results") or []:
        lines.append(f"- {r.get('binder_id')}: {r.get('outcome')} {r.get('reason', '')} (ruleset v{r.get('ruleset_version')})")
        for o in r.get("rule_outcomes", []):
            lines.append(f"  - {o.get('rule_id')}: {o.get('outcome')} value={o.get('value')} {o.get('reason', '')}")
    lines.append(f"## Recommendation: {record.get('recommendation')} scores={record.get('scores')}")
    d = record.get("decision") or {}
    lines.append(f"## Decision: {d.get('action')} -> {d.get('selected_binder')} by {d.get('underwriter_id')} at {d.get('decided_at')}")
    lines.append(f"## Settlement: {record.get('settlement')}")
    lines.append(f"## Models: {record.get('model_versions')} · timings: {record.get('stage_timings')}")
    return "\n".join(lines)
