"""Underwriter correction: resolve contested values, then re-evaluate (BFR-EXT-006/007).

The correction, corrector, timestamp, and pre-correction value are recorded
in field metadata and flow into the audit record. Nothing is overwritten
silently.
"""
# datetime: used to timestamp the correction.
from datetime import datetime, timedelta, timezone
# Any: type hint for corrections dict values.
from typing import Any


# apply: record a correction and return updated extracted + meta.
def apply(state: dict, corrections: dict[str, Any], underwriter_id: str) -> dict:
    # Copy extracted data.
    extracted = dict(state.get("extracted") or {})
    # Copy metadata, shallow-copying nested dicts.
    meta = {k: dict(v) if isinstance(v, dict) else v
            for k, v in (state.get("extracted_meta") or {}).items()}
    # Current UTC timestamp.
    now = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    # Apply each correction.
    for field, value in corrections.items():
        # Normalise money string to number.
        if field == "total_insured_value" and isinstance(value, str):
            try:
                value = float(value.replace("$", "").replace(",", "").strip())
            except ValueError:
                pass
        # Get existing metadata for the field (or empty).
        m = meta.get(field) or {}
        # Record pre-correction value.
        m["pre_correction_value"] = extracted.get(field)
        # Record who corrected.
        m["corrected_by"] = underwriter_id
        # Record when corrected.
        m["corrected_at"] = now
        # Set new value.
        m["value"] = value
        # Update present flag.
        m["present"] = value is not None
        # Clear contested flag.
        m["contested"] = False
        # Remove conflict list.
        m.pop("conflict", None)
        # Store updated metadata.
        meta[field] = m
        # Store corrected value in extracted.
        extracted[field] = value
    # Return updated state slice.
    return {"extracted": extracted, "extracted_meta": meta}
