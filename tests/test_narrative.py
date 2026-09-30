"""Narrative describes determined outcomes only (BFR-REC-007/008/010/011)."""
from nodes.narrative import summarize


def test_recommendation_case():
    st = {"submission_reference": "S", "extracted": {"broker_name": "B", "total_insured_value": 100},
          "binder_results": [
              {"binder_id": "A", "outcome": "Accept"},
              {"binder_id": "B", "outcome": "Decline",
               "rule_outcomes": [{"rule_id": "R1", "outcome": "Decline"}]}],
          "recommendation": "A", "scores": {"A": 8.0}}
    n = summarize(st)["narrative"]
    assert "Recommended binder: A with score 8.0" in n
    assert "advisory" in n and "R1" in n
    for banned in ("bound", "placed", "accepted"):
        assert banned not in n.lower()


def test_no_eligible_case():
    st = {"submission_reference": "S", "extracted": {},
          "binder_results": [{"binder_id": "B", "outcome": "Refer",
                              "rule_outcomes": [{"rule_id": "G1", "outcome": "Cannot assess"}]}],
          "recommendation": "no eligible binder", "scores": {}}
    n = summarize(st)["narrative"]
    assert "No binder is recommended" in n and "G1" in n
