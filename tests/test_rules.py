"""Per-rule bite / non-bite / Cannot-assess (BFR-NFR-034 trace)."""
from nodes.appetite import evaluate_rule

TIV = {"rule_id": "A-002-TIV", "field_reference": "total_insured_value", "operator": "lte", "threshold_value": 10_000_000}


def test_tiv_pass():
    assert evaluate_rule({"total_insured_value": 5_000_000}, TIV)["outcome"] == "Pass"


def test_tiv_decline():
    assert evaluate_rule({"total_insured_value": 20_000_000}, TIV)["outcome"] == "Decline"


def test_tiv_cannot_assess():
    assert evaluate_rule({}, TIV)["outcome"] == "Cannot assess"
