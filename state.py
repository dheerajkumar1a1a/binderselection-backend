"""Submission state - minimal 7.1/7.5 subset for vertical slice."""
from typing import TypedDict, Any


class SubmissionState(TypedDict, total=False):
    submission_reference: str
    documents: list[dict[str, Any]]
    extracted: dict[str, Any]
    extracted_meta: dict[str, Any]
    completeness: dict[str, Any]
    capacity_snapshot: dict[str, Any]
    rule_outcomes: list[dict[str, Any]]
    binder_outcome: str
    scores: dict[str, float]
    ranking: list[str]
    recommendation: str
    decision: dict[str, Any]
    audit_id: str
