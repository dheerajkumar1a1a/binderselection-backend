"""Gemini extraction: contract enforced on mocked HTTP (no key needed)."""
import nodes.extract_gemini as gm
from nodes.extract import extract


def test_drops_unknown_fields_and_marks_absent(monkeypatch):
    fake = {"fields": [
        {"name": "broker_name", "value": "Acme", "confidence": 0.9,
         "source_locator": "p1", "source_document_id": "d1"},
        {"name": "nonsense", "value": "x", "confidence": 1.0},
    ]}
    monkeypatch.setattr(gm, "_call", lambda texts, key, model: fake)
    ext, meta = gm.gemini_extract([{"doc_id": "d1", "text": "broker Acme"}], api_key="test")
    assert ext["broker_name"] == "Acme" and "nonsense" not in ext
    assert ext["total_insured_value"] is None
    assert meta["total_insured_value"]["present"] is False


def test_money_string_normalised(monkeypatch):
    fake = {"fields": [{"name": "total_insured_value", "value": "$2,500,000",
                        "confidence": 0.8, "source_locator": "dec"}]}
    monkeypatch.setattr(gm, "_call", lambda texts, key, model: fake)
    ext, meta = gm.gemini_extract([{"doc_id": "d1", "text": "tiv"}], api_key="test")
    assert ext["total_insured_value"] == 2_500_000.0
    assert meta["total_insured_value"]["original_value"] == "$2,500,000"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_FILE", raising=False)
    try:
        gm.gemini_extract([{"doc_id": "d1"}])
        assert False
    except RuntimeError as e:
        assert "GEMINI_API_KEY" in str(e)


def test_key_read_from_file(monkeypatch, tmp_path):
    # A key file is the preferred route: key never exported into the shell.
    key_file = tmp_path / "gemini.txt"
    key_file.write_text("AQ.test-key-from-file\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_FILE", str(key_file))
    seen = {}
    monkeypatch.setattr(gm, "_call",
                        lambda texts, key, model: seen.update(key=key) or {"fields": []})
    gm.gemini_extract([{"doc_id": "d1", "text": "t"}])
    assert seen["key"] == "AQ.test-key-from-file"


def test_no_candidates_raises(monkeypatch):
    # A blocked or empty response must fail loudly, never fabricate fields.
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"candidates": []}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    try:
        gm._call(["t"], "k", "gemini-3.5-flash-lite")
        assert False
    except RuntimeError as e:
        assert "no candidates" in str(e)


def test_node_routes_to_gemini(monkeypatch):
    monkeypatch.setattr("nodes.extract_gemini.gemini_extract",
                        lambda docs: ({"broker_name": "Z"}, {"broker_name": {"present": True}}))
    out = extract({"documents": [{"doc_id": "d1"}]}, llm="gemini")
    assert out["extracted"]["broker_name"] == "Z"
    assert out["model_versions"]["extraction"] == gm.DEFAULT_MODEL


def test_default_model_is_gemini_3_5_flash_lite():
    assert gm.DEFAULT_MODEL == "gemini-3.5-flash-lite"


def test_full_schema_validated(monkeypatch):
    fake = {"fields": [
        {"name": "total_insured_value", "value": 6500000, "confidence": 0.9,
         "source_locator": "tiv"},
        {"name": "coverage_sections", "value": [{"limit": "$2,000,000"}],
         "confidence": 0.8, "source_locator": "sec"},
        {"name": "expiring_premium_disclosed", "value": False,
         "confidence": 0.9, "source_locator": "not disclosed"},
        {"name": "largest_single_claim_amount", "value": "$6,000",
         "confidence": 0.9, "source_locator": "claim"},
    ]}
    monkeypatch.setattr(gm, "_call", lambda texts, key, model: fake)
    ext, meta = gm.gemini_extract([{"doc_id": "d1", "text": "t"}], api_key="test")
    assert ext["coverage_sections"] == [{"limit": 2000000.0}]
    assert ext["expiring_premium_disclosed"] is False
    assert ext["largest_single_claim_amount"] == 6000.0
    assert ext["valuation_basis"] is None
    assert meta["valuation_basis"]["present"] is False
    assert len(ext) == len(gm.FIELDS)
