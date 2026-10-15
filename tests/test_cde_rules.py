"""Binder C/D/E rulesets: every new rule bites, passes, and (where applicable) refers."""
from nodes import appetite as app
from nodes import derive as drv


def _eval(ext, binder_id):
    ext = drv.derive({"extracted": ext})["extracted"]
    return app.evaluate({"extracted": ext}, binder_id=binder_id, as_at="2026-10-15")


def _base_c():
    return {"total_insured_value": 1000000, "broker_name": "Acme",
            "locations": [{"address": "S", "sprinklered": True, "country": "US",
                           "construction_type": "MASONRY", "alarm_type": "HARDWIRED"}],
            "commodities": [{"commodity_type": "STEEL"}],
            "insured_state_province": "TX", "claim_count_5_years": 0,
            "valuation_basis_stated_clearly": True, "policy_term_months": 12,
            "profit_share_requested": False}


def test_c_clean_accepts():
    out = _eval(_base_c(), "binder_C")
    assert out["binder_outcome"] == "Accept", out["rule_outcomes"]
    assert out["ruleset_version"] == 1


def test_c_each_rule_bites():
    cases = [
        ({"insured_state_province": "CA"}, "C-001-CALIFORNIA"),
        ({"claim_count_5_years": 2}, "C-002-LOSSES-5Y"),
        ("NON-US", "C-003-US-ONLY"),
        ("FRAME-NO-HARDWIRED", "C-004-FRAME-ALARM"),
        ({"valuation_basis_stated_clearly": False}, "C-005-VALUATION-CLEAR"),
        ({"policy_term_months": 6}, "C-006-TERM-12M"),
        ({"profit_share_requested": True}, "C-007-PROFIT-SHARE"),
        ("FOUR-SITES", "C-008-LOCATION-COUNT"),
        ({"commodities": [{"commodity_type": "Fresh Produce"}]}, "C-009-FRESH-PRODUCE"),
    ]
    for hint, rid in cases:
        ext = _base_c()
        if hint == "NON-US":
            ext["locations"] = [{"address": "S", "sprinklered": True, "country": "DE",
                                 "construction_type": "MASONRY", "alarm_type": "HARDWIRED"}]
        elif hint == "FRAME-NO-HARDWIRED":
            ext["locations"] = [{"address": "S", "sprinklered": True, "country": "US",
                                 "construction_type": "FRAME", "alarm_type": "LOCAL"}]
        elif hint == "FOUR-SITES":
            ext["locations"] = [{"address": f"S{i}", "sprinklered": True, "country": "US",
                                 "construction_type": "MASONRY", "alarm_type": "HARDWIRED"}
                                for i in range(4)]
        else:
            ext.update(hint)
        out = _eval(ext, "binder_C")
        got = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
        assert got.get(rid) == "Decline", (hint, got)


def test_c_frame_with_hardwired_passes_and_cross_site_mix_passes():
    ext = _base_c()
    ext["locations"] = [{"address": "S", "sprinklered": True, "country": "US",
                         "construction_type": "FRAME", "alarm_type": "HARDWIRED"}]
    out = _eval(ext, "binder_C")
    assert {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}["C-004-FRAME-ALARM"] == "Pass"
    ext["locations"] = [
        {"address": "S1", "sprinklered": True, "country": "US",
         "construction_type": "FRAME", "alarm_type": "HARDWIRED"},
        {"address": "S2", "sprinklered": True, "country": "US",
         "construction_type": "MASONRY", "alarm_type": "LOCAL"}]
    out = _eval(ext, "binder_C")
    assert {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}["C-004-FRAME-ALARM"] == "Pass"


def _base_d():
    return {"total_insured_value": 2000000, "broker_name": "Acme",
            "locations": [{"address": "S", "sprinklered": True, "location_limit": 1000000}],
            "commodities": [{"commodity_type": "STEEL"}],
            "coverage_type": "ALL_RISK", "policy_term_months": 12,
            "prior_cargo_coverage_cancelled": False, "sov_complete": True,
            "deductible_options_count": 1, "broker_count": 1}


def test_d_clean_accepts():
    out = _eval(_base_d(), "binder_D")
    assert out["binder_outcome"] == "Accept", out["rule_outcomes"]


def test_d_each_rule_bites():
    cases = [
        ({"locations": [{"address": "S", "location_limit": 4000000}]}, "D-001-LOCATION-LIMIT"),
        ({"total_insured_value": 16000000}, "D-002-TIV"),
        ({"prior_cargo_coverage_cancelled": True}, "D-003-CANCELLED"),
        ({"coverage_type": "PORT_TO_PORT"}, "D-004a-COVERAGE-TYPE"),
        ({"policy_term_months": 6}, "D-004b-TERM-12M"),
        ({"sov_complete": False}, "D-005a-SOV-COMPLETE"),
        ({"deductible_options_count": 3}, "D-005b-DEDUCTIBLES"),
        ({"broker_count": 2}, "D-006-BROKER-COUNT"),
        ({"commodities": [{"commodity_type": "Watches"}]}, "D-007-JEWELRY"),
    ]
    for hint, rid in cases:
        ext = _base_d()
        ext.update(hint)
        out = _eval(ext, "binder_D")
        got = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
        assert got.get(rid) == "Decline", (hint, got)


def _base_e():
    return {"total_insured_value": 2000000, "broker_name": "Acme",
            "insured_state_province": "NY", "insured_postcode_zip": "10001",
            "locations": [{"address": "S", "sprinklered": True, "flood_tier": "TIER_1",
                           "construction_type": "MASONRY", "roofing_type": "SHINGLE",
                           "cctv_present": True, "alarm_present": True,
                           "year_built": 2005, "cope_details_complete": True}],
            "commodities": [{"commodity_type": "STEEL"}],
            "coverage_sections": [{"limit": 1000000}],
            "valuation_basis": "CIF+10%", "requested_inception_date": "2030-01-01",
            "loss_run_provided": True, "claim_count_3_years": 0}


def test_e_clean_accepts():
    out = _eval(_base_e(), "binder_E")
    assert out["binder_outcome"] == "Accept", out["rule_outcomes"]


def test_e_each_rule_bites():
    cases = [
        ({"coverage_sections": [{"limit": 5000000}]}, "E-001-SECTION-LIMIT"),
        ({"total_insured_value": 13000000}, "E-002-TIV"),
        ({"claim_count_3_years": 1}, "E-003-CLAIMS-3Y"),
        ({"insured_state_province": "FL"}, "E-004-FL-TX"),
        ("TIER3", "E-005-FLOOD-TIER"),
        ({"locations": [{"address": "S", "construction_type": "WOOD", "roofing_type": "SHINGLE",
                         "cctv_present": True, "alarm_present": True}]}, "E-006a-WOOD-FRAME"),
        ({"locations": [{"address": "S", "construction_type": "MASONRY", "roofing_type": "MIXED",
                         "cctv_present": True, "alarm_present": True}]}, "E-006b-MIXED-ROOF"),
        ({"locations": [{"address": "S", "construction_type": "MASONRY", "roofing_type": "SHINGLE",
                         "cctv_present": False, "alarm_present": True}]}, "E-006c-CCTV"),
        ({"locations": [{"address": "S", "construction_type": "MASONRY", "roofing_type": "SHINGLE",
                         "cctv_present": True, "alarm_present": False}]}, "E-006d-ALARM"),
        ({"valuation_basis": "AGREED_VALUE"}, "E-007-VALUATION"),
        ({"requested_inception_date": "2020-05-01"}, "E-008-INCEPTION"),
        ({"loss_run_provided": False}, "E-009a-LOSS-RUN"),
        ({"commodities": [{"commodity_type": "Bulk Chemicals"}]}, "E-011-CHEMICALS"),
    ]
    for hint, rid in cases:
        ext = _base_e()
        if hint == "TIER3":
            ext["locations"] = [{"address": "S", "flood_tier": "tier_3", "construction_type": "MASONRY",
                                 "roofing_type": "SHINGLE", "cctv_present": True, "alarm_present": True,
                                 "year_built": 2005, "cope_details_complete": True}]
        else:
            ext.update(hint)
        out = _eval(ext, "binder_E")
        got = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
        assert got.get(rid) == "Decline", (hint, got)


def test_e_missing_data_refers_never_declines():
    ext = _base_e()
    ext.pop("loss_run_provided")
    ext.pop("insured_postcode_zip")
    for loc in ext["locations"]:
        loc.pop("year_built")
    out = _eval(ext, "binder_E")
    got = {o["rule_id"]: o["outcome"] for o in out["rule_outcomes"]}
    assert got["E-009a-LOSS-RUN"] == "Cannot assess"
    assert got["E-009c-ZIP"] == "Cannot assess"
    assert got["E-010a-YEAR-BUILT"] == "Cannot assess"
    assert out["binder_outcome"] == "Refer"


def test_location_count_derived():
    out = drv.derive({"extracted": {"locations": [{}, {}, {}]}})["extracted"]
    assert out["location_count"] == 3
    out = drv.derive({"extracted": {"locations": [{}], "location_count": 9}})["extracted"]
    assert out["location_count"] == 9
