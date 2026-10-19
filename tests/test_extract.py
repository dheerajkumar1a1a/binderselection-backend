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


def test_live_llm_defers_to_machine_readable_data():
    # A live model must never re-derive values we already hold in a
    # machine-readable block: deterministic data wins over the LLM.
    docs = [{"doc_id": "d1", "structured_hint": {"total_insured_value": 5_000_000}}]
    out = extract({"documents": docs}, llm="nvidia")
    assert out["model_versions"]["extraction"] == "structured-data"
    assert out["extracted"]["total_insured_value"] == 5_000_000.0
