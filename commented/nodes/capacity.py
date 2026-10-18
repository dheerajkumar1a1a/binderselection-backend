# Commented reference copy of nodes/capacity.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Capacity screening: derived available = line - written - reserved (BFR-CAP-002)."""


# def screen(state: dict, authorised_line: float, written: float, reserved: float) -> dict:
#     available = authorised_line - written - reserved
#     tiv = (state.get("extracted") or {}).get("total_insured_value", 0) or 0
#     eligible = available > 0 and available >= tiv
#     reason = "eligible" if eligible else f"shortfall={tiv - available}"
#     snap = {
#         "authorised_line": authorised_line,
#         "written_to_date": written,
#         "reserved": reserved,
#         "available_capacity": available,
#     }
#     return {"capacity_snapshot": snap, "binder_outcome": "eligible" if eligible else f"excluded:{reason}"}


# def screen_safe(state: dict, authorised_line: float, written: float,
#                 reserved: float, binder_id: str = "binder_A",
#                 as_at: str | None = None) -> dict:
#     """Lifecycle gate (BFR-CAP-010) + explicit source failure (BFR-CAP-012).

#     A suspended/retired binder is excluded with a reason, never silently
#     omitted. A failure halts with a distinguishable reason, never a partial
#     evaluation presented as complete (BFR-NFR-018).
#     """
#     try:
#         import sys
#         from pathlib import Path
#         sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rules"))
#         from store import is_active
#         if not is_active(binder_id, as_at):
#             return {"capacity_snapshot": {}, "binder_outcome": "excluded:suspended-or-retired"}
#         return screen(state, authorised_line, written, reserved)
#     except Exception as e:
#         return {"capacity_snapshot": {}, "binder_outcome": f"failed:{type(e).__name__}:{e}"}
