# Commented reference copy of nodes/timing.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Stage timing wrapper (BFR-MI-006, BFR-NFR-022).

# Wraps a node so its wall duration is recorded into state["stage_timings"].
# Human-wait inside review is included and labelled as such downstream.
# """
# import time
# from typing import Any, Callable


# def timed(name: str, fn: Callable[[dict], dict]):
#     def wrapper(state: dict) -> dict[str, Any]:
#         t0 = time.perf_counter()
#         out = dict(fn(state))
#         timings = dict(state.get("stage_timings") or {})
#         timings[name] = round(time.perf_counter() - t0, 4)
#         out["stage_timings"] = timings
#         return out
#     wrapper.__name__ = f"timed_{name}"
#     return wrapper
