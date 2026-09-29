"""Capacity screening: derived available = line - written - reserved (BFR-CAP-002)."""


def screen(state: dict, authorised_line: float, written: float, reserved: float) -> dict:
    available = authorised_line - written - reserved
    tiv = (state.get("extracted") or {}).get("total_insured_value", 0) or 0
    eligible = available > 0 and available >= tiv
    reason = "eligible" if eligible else f"shortfall={tiv - available}"
    snap = {
        "authorised_line": authorised_line,
        "written_to_date": written,
        "reserved": reserved,
        "available_capacity": available,
    }
    return {"capacity_snapshot": snap, "binder_outcome": "eligible" if eligible else f"excluded:{reason}"}
