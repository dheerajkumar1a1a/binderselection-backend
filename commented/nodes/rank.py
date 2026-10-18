# Commented reference copy of nodes/rank.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Absolute scoring placeholder: stable per binder, not relative (BFR-REC-005)."""


# def score(state: dict) -> dict:
#     if state.get("binder_outcome") != "Accept":
#         return {"scores": {}, "ranking": [], "recommendation": "no eligible binder"}
#     scores = {"binder_A": 7.0}
#     return {"scores": scores, "ranking": ["binder_A"], "recommendation": "binder_A"}
