"""LangGraph vertical slice: extract -> derive -> completeness -> evaluate -> rank -> review -> settle -> audit."""
from langgraph.graph import StateGraph, END
from state import SubmissionState
from nodes import extract as ext
from nodes import derive as drv
from nodes import completeness as comp
from nodes import multibind as mb
from nodes import review as rev
from nodes import settle as stl
from persistence import get_checkpointer, write_audit


def build(checkpointer=None):
    g = StateGraph(SubmissionState)
    g.add_node("extract", ext.extract)
    g.add_node("derive", drv.derive)
    g.add_node("completeness", comp.check)
    g.add_node("evaluate", mb.evaluate_binders)
    g.add_node("rank", mb.rank)
    g.add_node("review", rev.review)
    g.add_node("settle", stl.settle)
    g.add_node("audit", write_audit)
    g.set_entry_point("extract")
    g.add_edge("extract", "derive")
    g.add_edge("derive", "completeness")
    g.add_conditional_edges(
        "completeness",
        lambda s: "evaluate" if s["completeness"]["can_evaluate"] else END,
    )
    g.add_edge("evaluate", "rank")
    g.add_edge("rank", "review")
    g.add_conditional_edges(
        "review",
        lambda s: "derive" if (s.get("decision") or {}).get("action") == "correct" else "settle",
    )
    g.add_edge("settle", "audit")
    g.add_edge("audit", END)
    return g.compile(checkpointer=checkpointer)
