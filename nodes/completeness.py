"""Completeness gate: missing mandatory data -> Refer, never Pass (BFR-APP-003)."""
MANDATORY = ["total_insured_value", "broker_name", "locations"]


def check(state: dict) -> dict:
    extracted = state.get("extracted", {})
    missing = [f for f in MANDATORY if extracted.get(f) in (None, "", [])]
    return {"completeness": {"missing": missing, "can_evaluate": not missing}}
