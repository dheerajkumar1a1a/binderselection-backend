"""Extraction envelope: provenance, absent handling, normalisation."""
from nodes.extract import extract


def test_absent_stays_absent():
    out = extract({"documents": [{"doc_id": "d1"}]})
    assert out["extracted"]["total_insured_value"] is None
    assert out["extracted_meta"]["total_insured_value"]["present"] is False


def test_money_normalised_with_provenance():
    docs = [{"doc_id": "d1", "structured_hint": {"total_insured_value": "$5,000,000"}}]
    out = extract({"documents": docs})
    assert out["extracted"]["total_insured_value"] == 5_000_000.0
    m = out["extracted_meta"]["total_insured_value"]
    assert m["original_value"] == "$5,000,000"
    assert m["source_document_id"] == "d1"
