"""Completeness gate: missing mandatory data -> Refer, never Pass (BFR-APP-003)."""
# MANDATORY: the three fields that must be present for evaluation to proceed.
MANDATORY = ["total_insured_value", "broker_name", "locations"]


# check: gate that decides whether the submission has enough data to evaluate.
def check(state: dict) -> dict:
    # Pull extracted risk data from state; default to empty dict if absent.
    extracted = state.get("extracted", {})
    # Pull extraction metadata (confidence, provenance, contested flags).
    meta = state.get("extracted_meta", {})
    # A field is missing if its value is None, empty string, or empty list.
    missing = [f for f in MANDATORY if extracted.get(f) in (None, "", [])]
    # Collect fields flagged as contested (conflicting sources) from metadata.
    contested = [f for f, m in meta.items()
                 if isinstance(m, dict) and m.get("contested")]
    # Return completeness result; can_evaluate is False if any mandatory field missing.
    return {"completeness": {"missing": missing, "contested": contested,
                             "can_evaluate": not missing}}
