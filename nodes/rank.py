"""Absolute scoring placeholder: stable per binder, not relative (BFR-REC-005)."""


# score: placeholder scoring node (superseded by multibind in production).
def score(state: dict) -> dict:
    # If not Accept, no eligible binder.
    if state.get("binder_outcome") != "Accept":
        return {"scores": {}, "ranking": [], "recommendation": "no eligible binder"}
    # Placeholder score for binder_A.
    scores = {"binder_A": 7.0}
    # Return placeholder result.
    return {"scores": scores, "ranking": ["binder_A"], "recommendation": "binder_A"}
