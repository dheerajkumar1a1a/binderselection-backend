"""Conflicts across documents + correction with re-evaluation (BFR-EXT-004/006/007)."""
from nodes.extract import stub_extract
from nodes.correct import apply
from nodes.review import validate


def test_conflict_records_both_provenances():
    docs = [{"doc_id": "d1", "structured_hint": {"total_insured_value": 5000000}},
            {"doc_id": "d2", "structured_hint": {"total_insured_value": 7000000}}]
    ext, meta = stub_extract(docs)
    assert ext["total_insured_value"] == 5000000.0
    assert meta["total_insured_value"]["contested"] is True
    assert meta["total_insured_value"]["conflict"] == [
        {"value": 5000000.0, "source_document_id": "d1"},
        {"value": 7000000.0, "source_document_id": "d2"}]


def test_no_conflict_when_agreeing():
    docs = [{"doc_id": "d1", "structured_hint": {"broker_name": "Acme"}},
            {"doc_id": "d2", "structured_hint": {"broker_name": "Acme"}}]
    _, meta = stub_extract(docs)
    assert meta["broker_name"].get("contested") is None


def test_correction_records_trail_and_clears():
    state = {"extracted": {"total_insured_value": 5000000.0},
             "extracted_meta": {"total_insured_value": {
                 "value": 5000000.0, "present": True, "contested": True,
                 "conflict": [{"value": 5000000.0, "source_document_id": "d1"}]}}}
    out = apply(state, {"total_insured_value": "$6,000,000"}, "u9")
    assert out["extracted"]["total_insured_value"] == 6000000.0
    m = out["extracted_meta"]["total_insured_value"]
    assert m["pre_correction_value"] == 5000000.0
    assert m["corrected_by"] == "u9" and "corrected_at" in m
    assert m["contested"] is False and "conflict" not in m


def test_correct_action_validates():
    st = {"recommendation": "binder_A"}
    d = validate(st, {"action": "correct", "underwriter_id": "u1",
                      "corrections": {"total_insured_value": 6000000}})
    assert d["valid"] and d["action"] == "correct"
    d2 = validate(st, {"action": "correct", "underwriter_id": "u1"})
    assert not d2["valid"]


def test_correction_flips_outcome():
    from nodes import appetite as app
    from nodes import derive as drv
    state = {"extracted": drv.derive({"extracted": {
        "total_insured_value": 20000000, "broker_name": "B",
        "locations": [{"sprinklered": True}],
        "commodities": [{"commodity_type": "STEEL"}],
        "coverage_sections": [{"limit": 1000000}],
        "valuation_basis": "CIF+10%", "coverage_type": "ALL_RISK",
        "requested_inception_date": "2030-01-01",
        "expiring_premium_disclosed": False,
        "insured_in_continental_us": True,
        "largest_single_claim_amount": 0, "total_claims_amount": 0}})["extracted"]}
    before = app.evaluate(state, binder_id="binder_A", as_at="2026-09-30")
    assert before["binder_outcome"] == "Decline"
    fixed = apply({**state, "extracted_meta": {}}, {"total_insured_value": 5000000}, "u1")
    after = app.evaluate(fixed, binder_id="binder_A", as_at="2026-09-30")
    assert after["binder_outcome"] == "Accept"
