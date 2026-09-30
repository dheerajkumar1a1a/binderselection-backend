"""Multi-binder: independent evaluation, absolute scoring, tie-break (BFR-APP-011, REC-003/005/006)."""
from nodes import multibind as mb
from nodes import appetite as app

RICH_B_LOC = {"territory": "TX", "wildfire_risk_score": 10, "fema_flood_zone": "X",
               "construction_type": "MASONRY", "alarm_present": True, "year_built": 2000}
RICH_B_SUB = {"prior_coverage_cancelled": False, "prior_coverage_non_renewed": False,
              "valuation_basis": "CIF+10%", "profit_share_requested": False,
              "no_claims_bonus_requested": False, "years_trading": 5}


def _clean_both():
    ext = {"total_insured_value": 1000000, "broker_name": "Acme",
           "locations": [{"address": "S", "sprinklered": True, **RICH_B_LOC}],
           "commodities": [{"commodity_type": "STEEL"}],
           "coverage_sections": [{"limit": 1000000}],
           "coverage_type": "ALL_RISK",
           "requested_inception_date": "2030-01-01",
           "expiring_premium_disclosed": False,
           "insured_in_continental_us": True,
           "largest_single_claim_amount": 0, "total_claims_amount": 0}
    ext.update(RICH_B_SUB)
    return ext


def test_b_and_group_passes_clean():
    out = app.evaluate({"extracted": _clean_both()}, binder_id="binder_B", as_at="2026-09-30")
    assert out["binder_outcome"] == "Accept", out["rule_outcomes"]


def test_and_group_bites_same_site_only():
    base = _clean_both()
    same = dict(base)
    same["locations"] = [{"address": "S", "sprinklered": True, **{**RICH_B_LOC, "construction_type": "FRAME", "alarm_present": False}}]
    out = app.evaluate({"extracted": same}, binder_id="binder_B", as_at="2026-09-30")
    groups = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
    assert groups.get("B-003-FRAME-ALARM") == "Decline"
    mixed = dict(base)
    mixed["locations"] = [
        {"address": "S1", "sprinklered": True, **{**RICH_B_LOC, "construction_type": "FRAME", "alarm_present": True}},
        {"address": "S2", "sprinklered": True, **{**RICH_B_LOC, "construction_type": "MASONRY", "alarm_present": False}}]
    out2 = app.evaluate({"extracted": mixed}, binder_id="binder_B", as_at="2026-09-30")
    groups2 = {o["rule_id"]: o["outcome"] for o in out2["rule_outcomes"]}
    assert groups2.get("B-003-FRAME-ALARM") == "Pass"


def test_b_declines_livestock_while_a_accepts():
    ext = _clean_both()
    ext["commodities"] = [{"commodity_type": "Livestock"}]
    res = mb.evaluate_binders({"extracted": ext}, ["binder_A", "binder_B"], as_at="2026-09-30")
    by_id = {r["binder_id"]: r for r in res["binder_results"]}
    assert by_id["binder_A"]["outcome"] == "Accept"
    assert by_id["binder_B"]["outcome"] == "Decline"
    scored = mb.score_binders(res["binder_results"])
    assert scored["ranking"] == ["binder_A"]
    assert scored["scores"]["binder_A"] == 8.333


def test_scores_stable_when_binder_removed():
    ext = _clean_both()
    full = mb.evaluate_binders({"extracted": ext}, ["binder_A", "binder_B"], as_at="2026-09-30")
    solo = mb.evaluate_binders({"extracted": ext}, ["binder_A"], as_at="2026-09-30")
    assert mb.score_binders(full["binder_results"])["scores"]["binder_A"] == \
        mb.score_binders(solo["binder_results"])["scores"]["binder_A"]


def test_tie_break_by_configured_order():
    reg = [{"binder_id": "binder_M", "strategic_classification": "standard"},
           {"binder_id": "binder_N", "strategic_classification": "standard"}]
    results = [
        {"binder_id": "binder_N", "outcome": "Accept",
         "capacity_snapshot": {"authorised_line": 10.0, "available_capacity": 5.0}},
        {"binder_id": "binder_M", "outcome": "Accept",
         "capacity_snapshot": {"authorised_line": 10.0, "available_capacity": 5.0}},
    ]
    assert mb.score_binders(results, registry=reg)["ranking"] == ["binder_M", "binder_N"]


def test_missing_geo_refers_not_accepts():
    ext = _clean_both()
    for loc in ext["locations"]:
        for k in ("territory", "wildfire_risk_score", "fema_flood_zone"):
            loc.pop(k, None)
    out = app.evaluate({"extracted": ext}, binder_id="binder_B", as_at="2026-09-30")
    assert out["binder_outcome"] == "Refer"
