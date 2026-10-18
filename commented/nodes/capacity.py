"""Capacity screening: derived available = line - written - reserved (BFR-CAP-002)."""


# screen: basic capacity check (available vs TIV).
def screen(state: dict, authorised_line: float, written: float, reserved: float) -> dict:
    # Available = authorised - written - reserved.
    available = authorised_line - written - reserved
    # TIV from extracted data.
    tiv = (state.get("extracted") or {}).get("total_insured_value", 0) or 0
    # Eligible if available > 0 and covers TIV.
    eligible = available > 0 and available >= tiv
    # Reason string for excluded case.
    reason = "eligible" if eligible else f"shortfall={tiv - available}"
    # Snapshot of capacity figures.
    snap = {
        "authorised_line": authorised_line,
        "written_to_date": written,
        "reserved": reserved,
        "available_capacity": available,
    }
    # Return snapshot + outcome.
    return {"capacity_snapshot": snap, "binder_outcome": "eligible" if eligible else f"excluded:{reason}"}


# screen_safe: lifecycle gate + source-failure safety.
def screen_safe(state: dict, authorised_line: float, written: float,
                reserved: float, binder_id: str = "binder_A",
                as_at: str | None = None) -> dict:
    # Try lifecycle check then screen.
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rules"))
        from store import is_active
        # Suspended/retired → excluded with reason.
        if not is_active(binder_id, as_at):
            return {"capacity_snapshot": {}, "binder_outcome": "excluded:suspended-or-retired"}
        return screen(state, authorised_line, written, reserved)
    except Exception as e:
        # Source failure → failed with distinguishable reason.
        return {"capacity_snapshot": {}, "binder_outcome": f"failed:{type(e).__name__}:{e}"}
