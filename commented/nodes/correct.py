# Commented reference copy of nodes/correct.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Underwriter correction: resolve contested values, then re-evaluate (BFR-EXT-006/007).

# The correction, corrector, timestamp, and pre-correction value are recorded
# in field metadata and flow into the audit record. Nothing is overwritten
# silently.
# """
# from datetime import datetime, timezone
# from typing import Any


# def apply(state: dict, corrections: dict[str, Any], underwriter_id: str) -> dict:
#     extracted = dict(state.get("extracted") or {})
#     meta = {k: dict(v) if isinstance(v, dict) else v
#             for k, v in (state.get("extracted_meta") or {}).items()}
#     now = datetime.now(timezone.utc).isoformat()
#     for field, value in corrections.items():
#         if field == "total_insured_value" and isinstance(value, str):
#             try:
#                 value = float(value.replace("$", "").replace(",", "").strip())
#             except ValueError:
#                 pass
#         m = meta.get(field) or {}
#         m["pre_correction_value"] = extracted.get(field)
#         m["corrected_by"] = underwriter_id
#         m["corrected_at"] = now
#         m["value"] = value
#         m["present"] = value is not None
#         m["contested"] = False
#         m.pop("conflict", None)
#         meta[field] = m
#         extracted[field] = value
#     return {"extracted": extracted, "extracted_meta": meta}
