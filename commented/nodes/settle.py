# Commented reference copy of nodes/settle.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Settle node: reserve on accept/override, release on refer_back (BFR-CAP-008)."""
# from capacity import ledger as L


# def settle(state: dict) -> dict:
#     decision = state.get("decision") or {}
#     ref = state.get("submission_reference", "")
#     tiv = (state.get("extracted") or {}).get("total_insured_value") or 0
#     if not decision.get("valid"):
#         return {"settlement": {"action": "none", "reason": "no valid decision"}}
#     if decision.get("action") in ("accept", "override"):
#         binder = decision.get("selected_binder")
#         try:
#             r = L.reserve(binder, ref, float(tiv))
#             return {"settlement": {"action": "reserved", "binder": binder, **r}}
#         except ValueError as e:
#             return {"settlement": {"action": "failed", "error": str(e)}}
#     if decision.get("action") == "refer_back":
#         out = {}
#         for b in L.load().get("binders", {}):
#             out[b] = L.release(ref, b)
#         return {"settlement": {"action": "released", "detail": out}}
#     return {"settlement": {"action": "none"}}
