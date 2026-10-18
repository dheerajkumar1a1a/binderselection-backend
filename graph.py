"""LangGraph vertical slice: parse -> extract -> derive -> completeness -> evaluate -> rank -> review -> settle -> audit.

This module defines the orchestration flow for the binder selection workflow.
Each node represents a single processing step in the submission lifecycle:
- extract: parse the incoming submission
- derive: infer any missing or derived data
- completeness: decide whether the submission is ready to evaluate
- evaluate: score candidate binders
- rank: order the binder options by quality
- narrative: build a human-readable summary
- review: allow a reviewer to validate or correct the result
- settle: finalize the decision
- audit: persist the full execution record

The graph is compiled into a LangGraph workflow that can optionally use a
checkpointer to resume or inspect state across steps.
"""
# StateGraph, END: LangGraph primitives.
from langgraph.graph import StateGraph, END
# SubmissionState: typed state contract.
from state import SubmissionState
# Node modules.
from nodes import extract as ext
from nodes import derive as drv
from nodes import completeness as comp
from nodes import multibind as mb
from nodes import narrative as nar
from nodes import review as rev
from nodes import settle as stl
from nodes import timing as tmg
from nodes import parse as prs
# Persistence helpers.
from persistence import get_checkpointer, write_audit


# build: construct and compile the workflow graph.
def build(checkpointer=None):
    # Create graph with state schema.
    g = StateGraph(SubmissionState)

    # Register nodes (each wrapped in timing).
    g.add_node("parse", tmg.timed("parse", lambda s: prs.parse_documents(s.get("documents") or [])))
    g.add_node("extract", tmg.timed("extract", ext.extract))
    g.add_node("derive", tmg.timed("derive", drv.derive))
    g.add_node("completeness", tmg.timed("completeness", comp.check))
    g.add_node("evaluate", tmg.timed("evaluate", mb.evaluate_binders))
    g.add_node("rank", tmg.timed("rank", mb.rank))
    g.add_node("narrative", tmg.timed("narrative", nar.summarize))
    g.add_node("review", tmg.timed("review", rev.review))
    g.add_node("settle", tmg.timed("settle", stl.settle))
    g.add_node("audit", tmg.timed("audit", write_audit))

    # Entry point.
    g.set_entry_point("parse")

    # Parse: halt on limit breach, else continue.
    g.add_conditional_edges(
        "parse",
        lambda s: END if (s.get("parse") or {}).get("halted") else "extract",
    )

    # Linear flow to completeness gate.
    g.add_edge("extract", "derive")
    g.add_edge("derive", "completeness")

    # Completeness gate.
    g.add_conditional_edges(
        "completeness",
        lambda s: "evaluate" if s["completeness"]["can_evaluate"] else END,
    )

    # Evaluation pipeline.
    g.add_edge("evaluate", "rank")
    g.add_edge("rank", "narrative")
    g.add_edge("narrative", "review")

    # Review: correct → derive (re-evaluate), else settle.
    g.add_conditional_edges(
        "review",
        lambda s: "derive" if (s.get("decision") or {}).get("action") == "correct" else "settle",
    )

    # Finalization + audit.
    g.add_edge("settle", "audit")
    g.add_edge("audit", END)

    # Compile with optional checkpointer.
    return g.compile(checkpointer=checkpointer)
