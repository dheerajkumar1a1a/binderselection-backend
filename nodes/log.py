"""Structured logs that never carry submission content (BFR-NFR-003/024)."""
import json

BLOCKED = {"text", "documents", "extracted", "extracted_meta", "prompt",
           "original_value", "value", "conflict"}


def safe_event(event: str, **fields) -> str:
    clean = {k: ("[redacted]" if k in BLOCKED else v) for k, v in fields.items()}
    return json.dumps({"event": event, **clean})
