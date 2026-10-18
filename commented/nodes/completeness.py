# Commented reference copy of nodes/completeness.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Completeness gate: missing mandatory data -> Refer, never Pass (BFR-APP-003)."""
# MANDATORY = ["total_insured_value", "broker_name", "locations"]


# def check(state: dict) -> dict:
#     extracted = state.get("extracted", {})
#     meta = state.get("extracted_meta", {})
#     missing = [f for f in MANDATORY if extracted.get(f) in (None, "", [])]
#     contested = [f for f, m in meta.items()
#                  if isinstance(m, dict) and m.get("contested")]
#     return {"completeness": {"missing": missing, "contested": contested,
#                              "can_evaluate": not missing}}
