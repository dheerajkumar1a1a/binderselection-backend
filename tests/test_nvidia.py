"""NVIDIA extraction: contract enforced on mocked HTTP (no key needed)."""
import nodes.extract_nvidia as nv
from nodes.extract import extract


def test_drops_unknown_fields_and_marks_absent(monkeypatch):
    fake = {"fields": [
        {"name": "broker_name", "value": "Acme", "confidence": 0.9,
         "source_locator": "p1", "source_document_id": "d1"},
        {"name": "nonsense", "value": "x", "confidence": 1.0},
    ]}
    monkeypatch.setattr(nv, "_call", lambda texts, key, model: fake)
    docs = [{"doc_id": "d1", "text": "broker Acme"}]
    ext, meta = nv.nvidia_extract(docs, api_key="test")
    assert ext["broker_name"] == "Acme" and "nonsense" not in ext
    assert ext["total_insured_value"] is None
    assert meta["total_insured_value"]["present"] is False


def test_money_string_normalised(monkeypatch):
    fake = {"fields": [{"name": "total_insured_value", "value": "$2,500,000",
                        "confidence": 0.8, "source_locator": "dec"}]}
    monkeypatch.setattr(nv, "_call", lambda texts, key, model: fake)
    ext, meta = nv.nvidia_extract([{"doc_id": "d1", "text": "tiv"}], api_key="test")
    assert ext["total_insured_value"] == 2_500_000.0
    assert meta["total_insured_value"]["original_value"] == "$2,500,000"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    try:
        nv.nvidia_extract([{"doc_id": "d1"}])
        assert False
    except RuntimeError as e:
        assert "NVIDIA_API_KEY" in str(e)


def test_node_routes_to_nvidia(monkeypatch):
    monkeypatch.setattr("nodes.extract_nvidia.nvidia_extract",
                        lambda docs: ({"broker_name": "Z"}, {"broker_name": {"present": True}}))
    out = extract({"documents": [{"doc_id": "d1"}]}, llm="nvidia")
    assert out["extracted"]["broker_name"] == "Z"
    assert out["model_versions"]["extraction"] == nv.DEFAULT_MODEL


def test_default_model_is_nemotron_120b():
    assert nv.DEFAULT_MODEL == "nvidia/nemotron-3-super-120b-a12b"
