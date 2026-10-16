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
from nodes import parse as prs
from persistence import get_checkpointer, write_audit


# Build the workflow graph for handling submissions.
# The StateGraph keeps the shared state object passed between nodes.
def build(checkpointer=None):
    # Create the graph and initialize the shared state schema.
    g = StateGraph(SubmissionState)

    # Register each pipeline stage as a node.
    # Each node is wrapped in a timing decorator to measure execution time.
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

    # Start the workflow from the parsing step.
    g.set_entry_point("parse")

    # Parse first; a limit breach halts everything, anything else continues
    # with per-document statuses riding along for the underwriter.
    g.add_conditional_edges(
        "parse",
        lambda s: END if (s.get("parse") or {}).get("halted") else "extract",
    )

    # Linear flow until the completeness gate.
    g.add_edge("extract", "derive")
    g.add_edge("derive", "completeness")

    # Decide whether the submission has enough information to evaluate binders.
    # If not, stop the workflow early; otherwise continue to evaluation.
    g.add_conditional_edges(
        "completeness",
        lambda s: "evaluate" if s["completeness"]["can_evaluate"] else END,
    )

    # Evaluation pipeline: score candidates, then rank them, then summarize.
    g.add_edge("evaluate", "rank")
    g.add_edge("rank", "narrative")
    g.add_edge("narrative", "review")

    # Review step decides whether to loop back for correction or proceed to final settlement.
    # If the reviewer marks the decision as "correct", restart derivation so the state can be
    # re-derived or corrected before finalizing. Otherwise, continue to settle.
    g.add_conditional_edges(
        "review",
        lambda s: "derive" if (s.get("decision") or {}).get("action") == "correct" else "settle",
    )

    # Finalization and auditing.
    g.add_edge("settle", "audit")
    g.add_edge("audit", END)

    # Compile the graph with an optional checkpointer for persistence / resume support.
    return g.compile(checkpointer=checkpointer)
