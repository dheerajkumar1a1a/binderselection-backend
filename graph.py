"""LangGraph vertical slice: extract -> derive -> completeness -> evaluate -> rank -> review -> settle -> audit."""
from langgraph.graph import StateGraph, END
from state import SubmissionState
from nodes import extract as ext
from nodes import derive as drv
from nodes import completeness as comp
from nodes import multibind as mb
from nodes import narrative as nar
from nodes import review as rev
from nodes import settle as stl
from nodes import timing as tmg
from persistence import get_checkpointer, write_audit


def build(checkpointer=None):
    g = StateGraph(SubmissionState)
    g.add_node("extract", tmg.timed("extract", ext.extract))
    g.add_node("derive", tmg.timed("derive", drv.derive))
    g.add_node("completeness", tmg.timed("completeness", comp.check))
    g.add_node("evaluate", tmg.timed("evaluate", mb.evaluate_binders))
    g.add_node("rank", tmg.timed("rank", mb.rank))
    g.add_node("narrative", tmg.timed("narrative", nar.summarize))
    g.add_node("review", tmg.timed("review", rev.review))
    g.add_node("settle", tmg.timed("settle", stl.settle))
    g.add_node("audit", tmg.timed("audit", write_audit))
    g.set_entry_point("extract")
    g.add_edge("extract", "derive")
    g.add_edge("derive", "completeness")
    g.add_conditional_edges(
        "completeness",
        lambda s: "evaluate" if s["completeness"]["can_evaluate"] else END,
    )
    g.add_edge("evaluate", "rank")
    g.add_edge("rank", "narrative")
    g.add_edge("narrative", "review")
    g.add_conditional_edges(
        "review",
        lambda s: "derive" if (s.get("decision") or {}).get("action") == "correct" else "settle",
    )
    g.add_edge("settle", "audit")
    g.add_edge("audit", END)
    return g.compile(checkpointer=checkpointer)
