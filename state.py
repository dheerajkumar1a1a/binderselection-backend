"""Submission state - minimal 7.1/7.5 subset for vertical slice."""
from typing import TypedDict, Any


class SubmissionState(TypedDict, total=False):
    submission_reference: str
    documents: list[dict[str, Any]]
    parse: dict[str, Any]
    extracted: dict[str, Any]
    extracted_meta: dict[str, Any]
    completeness: dict[str, Any]
    capacity_snapshot: dict[str, Any]
    rule_outcomes: list[dict[str, Any]]
    binder_outcome: str
    binder_results: list[dict[str, Any]]
    rulesets: dict[str, Any]
    scores: dict[str, float]
    ranking: list[str]
    recommendation: str
    decision: dict[str, Any]
    settlement: dict[str, Any]
    narrative: str
    stage_timings: dict[str, float]
    model_versions: dict[str, Any]
    supersedes: str | None
    audit_id: str
