"""Full operator set + Binder A v2 end-to-end (9/9 Appendix-A rules)."""
from nodes.appetite import evaluate_rule, evaluate

CLEAN = {"coverage_sections": [{"limit": 1000000}], "total_insured_value": 1000000,
         "largest_single_claim_amount": 0, "total_claims_amount": 0,
         "insured_in_continental_us": True, "locations": [{"sprinklered": True}],
         "valuation_basis": "CIF+10%", "coverage_type": "ALL_RISK",
         "requested_inception_date": "2030-01-01",
         "expiring_premium_disclosed": False,
         "commodities": [{"commodity_type": "STEEL"}]}


def test_operators():
    assert evaluate_rule({"a": 5}, {"rule_id": "R", "field_reference": "a", "operator": "gt", "threshold_value": 4})["outcome"] == "Pass"
    assert evaluate_rule({"a": 3}, {"rule_id": "R", "field_reference": "a", "operator": "gt", "threshold_value": 4})["outcome"] == "Decline"
    assert evaluate_rule({"a": 5}, {"rule_id": "R", "field_reference": "a", "operator": "gte", "threshold_value": 5})["outcome"] == "Pass"
    assert evaluate_rule({"a": "X"}, {"rule_id": "R", "field_reference": "a", "operator": "eq", "threshold_value": "X"})["outcome"] == "Pass"
    assert evaluate_rule({"a": "X"}, {"rule_id": "R", "field_reference": "a", "operator": "neq", "threshold_value": "Y"})["outcome"] == "Pass"
    assert evaluate_rule({"a": False}, {"rule_id": "R", "field_reference": "a", "operator": "is_false"})["outcome"] == "Pass"
    assert evaluate_rule({"a": "2020-01-01"}, {"rule_id": "R", "field_reference": "a", "operator": "before", "threshold_value": "2030-01-01"})["outcome"] == "Pass"
    assert evaluate_rule({"a": "2030-01-01"}, {"rule_id": "R", "field_reference": "a", "operator": "after", "threshold_value": "TODAY"})["outcome"] == "Pass"


def test_v2_clean_accepts():
    out = evaluate({"extracted": CLEAN}, binder_id="binder_A", as_at="2026-09-30")
    assert out["binder_outcome"] == "Accept", out["rule_outcomes"]
    assert out["ruleset_version"] == 2


def test_v2_each_new_rule_bites():
    cases = [
        ({"coverage_sections": [{"limit": 6000000}]}, "A-001-SECTION-LIMIT"),
        ({"losses": [{"loss_date": "2024-01-01", "paid_incurred_amount": 6000}]}, None),  # via derive below
        ({"valuation_basis": "Selling Price"}, "A-006-VALUATION"),
        ({"coverage_type": "PORT_TO_PORT"}, "A-007a-COVERAGE-TYPE"),
        ({"requested_inception_date": "2020-05-01"}, "A-007b-INCEPTION"),
        ({"expiring_premium_disclosed": True}, "A-008-EXPIRING-PREMIUM"),
    ]
    from nodes.derive import derive
    for hint, rid in cases:
        ext = dict(CLEAN)
        ext.update(hint)
        if "losses" in hint:
            for k in ("largest_single_claim_amount", "total_claims_amount",
                      "claim_count_3_years", "claim_count_5_years"):
                ext.pop(k, None)
            ext = derive({"extracted": ext}, as_at="2026-09-30")["extracted"]
            out = evaluate({"extracted": ext}, binder_id="binder_A", as_at="2026-09-30")
            got = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
            assert got.get("A-003a-SINGLE-CLAIM") == "Decline", hint
            continue
        out = evaluate({"extracted": ext}, binder_id="binder_A", as_at="2026-09-30")
        got = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
        assert got.get(rid) == "Decline", (hint, got)
