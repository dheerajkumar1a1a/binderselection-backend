"""LangGraph vertical slice: extract -> completeness -> capacity -> appetite -> rank -> review -> audit."""
from langgraph.graph import StateGraph, END
from state import SubmissionState
from nodes import extract as ext
from nodes import completeness as comp
from nodes import capacity as cap
from nodes import appetite as app
from nodes import rank as rnk
from nodes import review as rev
from persistence import get_checkpointer, write_audit

CAP_LINE, CAP_WRITTEN, CAP_RESERVED = 15_000_000.0, 5_000_000.0, 0.0


def build(checkpointer=None):
    g = StateGraph(SubmissionState)
    g.add_node("extract", ext.extract)
    g.add_node("completeness", comp.check)
    g.add_node("capacity", lambda s: cap.screen(s, CAP_LINE, CAP_WRITTEN, CAP_RESERVED))
    g.add_node("appetite", app.evaluate)
    g.add_node("rank", rnk.score)
    g.add_node("review", rev.review)
    g.add_node("audit", write_audit)
    g.set_entry_point("extract")
    g.add_edge("extract", "completeness")
    g.add_conditional_edges(
        "completeness",
        lambda s: "capacity" if s["completeness"]["can_evaluate"] else END,
    )
    g.add_conditional_edges(
        "capacity",
        lambda s: "appetite" if s["binder_outcome"] == "eligible" else END,
    )
    g.add_edge("appetite", "rank")
    g.add_edge("rank", "review")
    g.add_edge("review", "audit")
    g.add_edge("audit", END)
    return g.compile(checkpointer=checkpointer)
