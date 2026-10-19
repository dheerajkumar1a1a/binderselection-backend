"""Guard: the published Pages schema must match the Python extractor's schema.

A silent mismatch is how the demo started dropping locations, claim counts and
postcodes, which made binder E impossible to Accept in the browser. This test
fails the build the moment the two drift apart.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "docs" / "data" / "extract-schema.json"


def _schema_module():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from nodes import extract_gemini
    return extract_gemini


def test_published_schema_exists():
    assert PUBLISHED.exists(), "run scripts/publish_extract_schema.py"


def test_fields_match_python():
    mod = _schema_module()
    got = json.loads(PUBLISHED.read_text(encoding="utf-8"))["fields"]
    assert got == mod.FIELDS, (
        f"published fields differ from nodes.extract_gemini.FIELDS "
        f"(published {len(got)}, python {len(mod.FIELDS)})")


def test_prompt_matches_python():
    mod = _schema_module()
    got = json.loads(PUBLISHED.read_text(encoding="utf-8"))["prompt"]
    assert got == mod.PROMPT, "published prompt differs from nodes.extract_gemini.PROMPT"


def test_schema_is_at_least_as_broad_as_python():
    """The demo must never be narrower than the engine's appetite rules need."""
    mod = _schema_module()
    got = json.loads(PUBLISHED.read_text(encoding="utf-8"))["fields"]
    for name in ("locations", "claim_count_3_years", "claim_count_5_years",
                 "loss_run_provided", "insured_postcode_zip"):
        assert name in got, f"published schema is missing {name}"


def test_demo_uses_published_schema():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "data/extract-schema.json" in html, "demo does not load the published schema"
    assert "SCHEMA.prompt" in html, "demo live extractors do not use the published prompt"
    assert "SCHEMA.fields" in html, "demo field mapping does not use the published field list"