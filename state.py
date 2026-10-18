"""Submission state - minimal 7.1/7.5 subset for vertical slice."""
# TypedDict: typed dictionary for state.
# Any: generic type.
from typing import TypedDict, Any


# SubmissionState: typed state contract shared across nodes.
class SubmissionState(TypedDict, total=False):
    # Submission reference id.
    submission_reference: str
    # Input documents.
    documents: list[dict[str, Any]]
    # Parse result.
    parse: dict[str, Any]
    # Extracted risk data.
    extracted: dict[str, Any]
    # Extraction metadata (confidence, provenance).
    extracted_meta: dict[str, Any]
    # Completeness gate result.
    completeness: dict[str, Any]
    # Capacity snapshot.
    capacity_snapshot: dict[str, Any]
    # Rule outcomes.
    rule_outcomes: list[dict[str, Any]]
    # Binder-level outcome.
    binder_outcome: str
    # Per-binder results.
    binder_results: list[dict[str, Any]]
    # Loaded rulesets.
    rulesets: dict[str, Any]
    # Scores.
    scores: dict[str, float]
    # Ranking list.
    ranking: list[str]
    # Recommended binder.
    recommendation: str
    # Underwriter decision.
    decision: dict[str, Any]
    # Settlement result.
    settlement: dict[str, Any]
    # Narrative text.
    narrative: str
    # Stage timings.
    stage_timings: dict[str, float]
    # Model versions used.
    model_versions: dict[str, Any]
    # Supersedes link.
    supersedes: str | None
    # Audit id.
    audit_id: str
