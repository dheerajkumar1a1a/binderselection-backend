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
    }
    with open(audit_dir / "decisions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return {"audit_id": record["evaluation_id"]}
