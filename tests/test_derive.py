"""Derived fields computed from raw losses/dates/address (BFR 7.1.6)."""
from nodes.derive import derive


def test_loss_aggregates_from_losses():
    out = derive({"extracted": {"losses": [
        {"loss_date": "2024-06-01", "paid_incurred_amount": 6000},
        {"loss_date": "2020-01-01", "paid_incurred_amount": 3000}]}},
        as_at="2026-09-30")["extracted"]
    assert out["largest_single_claim_amount"] == 6000
    assert out["total_claims_amount"] == 9000
    assert out["claim_count_3_years"] == 1
    assert out["claim_count_5_years"] == 1


def test_explicit_derived_values_untouched():
    out = derive({"extracted": {"losses": [{"loss_date": "2024-01-01", "paid_incurred_amount": 1}],
                                           "largest_single_claim_amount": 999}})["extracted"]
    assert out["largest_single_claim_amount"] == 999


def test_continental_us():
    assert derive({"extracted": {"insured_country": "US", "insured_state_province": "TX"}})["extracted"]["insured_in_continental_us"] is True
    assert derive({"extracted": {"insured_country": "US", "insured_state_province": "PR"}})["extracted"]["insured_in_continental_us"] is False
    assert derive({"extracted": {"insured_country": "DE", "insured_state_province": ""}})["extracted"]["insured_in_continental_us"] is False


def test_years_trading():
    out = derive({"extracted": {"business_commencement_date": "2020-01-01"}}, as_at="2026-01-01")["extracted"]
    assert out["years_trading"] == 6.0
