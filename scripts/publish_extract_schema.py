"""Publish the canonical extraction schema for the Pages demo.

The demo's live extractors must ask the model for exactly the same fields the
Python extractor does, otherwise it silently drops fields that binder rules
depend on (locations, claim counts, loss run, postcode) and the demo can never
reach an Accept that the engine reaches locally.

Writes docs/data/extract-schema.json straight from nodes/extract_gemini.py so
there is one source of truth. tests/test_extract_schema.py fails if this file
ever drifts from the module.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Imported for their side effect of being the single source of truth.
from nodes.extract_gemini import DEFAULT_MODEL, FIELDS, PROMPT  # noqa: E402

OUT = ROOT / "docs" / "data" / "extract-schema.json"


def schema() -> dict:
    """Build the published schema payload."""
    return {"model_default": DEFAULT_MODEL, "field_count": len(FIELDS),
            "fields": FIELDS, "prompt": PROMPT}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(FIELDS)} fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())