"""Structured logs that never carry submission content (BFR-NFR-003/024)."""
# json: used to serialise log lines.
import json

# BLOCKED: field names whose values must never appear in logs.
BLOCKED = {"text", "documents", "extracted", "extracted_meta", "prompt",
           "original_value", "value", "conflict"}


# safe_event: build a JSON log line with blocked fields redacted.
def safe_event(event: str, **fields) -> str:
    # Replace value with "[redacted]" for any blocked key; keep others.
    clean = {k: ("[redacted]" if k in BLOCKED else v) for k, v in fields.items()}
    # Return serialised JSON log line including event name.
    return json.dumps({"event": event, **clean})
