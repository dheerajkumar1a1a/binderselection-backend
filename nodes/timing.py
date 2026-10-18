"""Stage timing wrapper (BFR-MI-006, BFR-NFR-022).

Wraps a node so its wall duration is recorded into state["stage_timings"].
Human-wait inside review is included and labelled as such downstream.
"""
# time: used to measure wall-clock duration.
import time
# typing helpers for the wrapper signature.
from typing import Any, Callable


# timed: wrap a node function to record its execution duration.
def timed(name: str, fn: Callable[[dict], dict]):
    # wrapper: the timed version of the node.
    def wrapper(state: dict) -> dict[str, Any]:
        # Start timer.
        t0 = time.perf_counter()
        # Run the original node.
        out = dict(fn(state))
        # Copy existing timings (or empty dict).
        timings = dict(state.get("stage_timings") or {})
        # Record this stage's elapsed time, rounded.
        timings[name] = round(time.perf_counter() - t0, 4)
        # Attach timings to output.
        out["stage_timings"] = timings
        # Return enriched output.
        return out
    # Preserve a readable name for the wrapper.
    wrapper.__name__ = f"timed_{name}"
    # Return the wrapper.
    return wrapper
