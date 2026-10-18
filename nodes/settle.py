"""Settle node: reserve on accept/override, release on refer_back (BFR-CAP-008)."""
# Import the capacity ledger module.
from capacity import ledger as L


# settle: reserve capacity on accept/override, release on refer_back.
def settle(state: dict) -> dict:
    # Get the underwriter decision.
    decision = state.get("decision") or {}
    # Submission reference for ledger keying.
    ref = state.get("submission_reference", "")
    # Total insured value to reserve.
    tiv = (state.get("extracted") or {}).get("total_insured_value") or 0
    # No valid decision → nothing to settle.
    if not decision.get("valid"):
        return {"settlement": {"action": "none", "reason": "no valid decision"}}
    # Accept/override → reserve capacity for selected binder.
    if decision.get("action") in ("accept", "override"):
        binder = decision.get("selected_binder")
        try:
            r = L.reserve(binder, ref, float(tiv))
            return {"settlement": {"action": "reserved", "binder": binder, **r}}
        except ValueError as e:
            return {"settlement": {"action": "failed", "error": str(e)}}
    # Refer back → release any prior reservation.
    if decision.get("action") == "refer_back":
        out = {}
        for b in L.load().get("binders", {}):
            out[b] = L.release(ref, b)
        return {"settlement": {"action": "released", "detail": out}}
    # Other actions → no settlement.
    return {"settlement": {"action": "none"}}
