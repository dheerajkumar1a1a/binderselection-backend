"""verify_fixture_uploads.py - prove uploaded fixtures reproduce the dropdown.

For every sample case in samples/manifest.json and every supported fixture
format (pdf, docx, eml) this runs the real UI pipeline path with a *live* LLM
selected and no API key set. The generated fixtures embed a machine-readable
submission block, so the extractor must short-circuit to the deterministic
"structured-data" path (it must never need a model to read our own fixtures).

It then checks that the uploaded fixture's recommendation and per-binder
outcomes are byte-identical to picking the same case from the UI dropdown.

Usage:
    .venv\\Scripts\\python.exe scripts\\verify_fixture_uploads.py

Exit code is non-zero on any mismatch, so it doubles as a regression gate.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# Force the keyless path: if the short-circuit works no model is ever called.
for _k in ("NVIDIA_API_KEY", "NVIDIA_MODEL", "OPENROUTER_API_KEY", "OPENROUTER_MODEL"):
    os.environ.pop(_k, None)

from ui.app import _case_by_id, run_pipeline  # noqa: E402

FORMATS = ("pdf", "docx", "eml")


def _summary(state: dict) -> tuple:
    """Recommendation plus per-binder outcomes - the observable result."""
    return (
        state.get("recommendation"),
        {r["binder_id"]: r["outcome"] for r in state.get("binder_results", [])},
    )


def main() -> int:
    manifest = json.loads((REPO / "samples" / "manifest.json").read_text(encoding="utf-8"))
    total = mismatches = 0
    for case_meta in manifest["cases"]:
        case_id = case_meta["id"]
        case = _case_by_id(case_id)
        if not case:
            print(f"!! case not found: {case_id}")
            mismatches += 1
            continue
        # Baseline: the dropdown path (pre-labelled sample data, stub extractor).
        want = _summary(run_pipeline(case["documents"], f"CHK-{case_id}", llm=None))
        stem = "case-" + Path(case_meta["file"]).stem
        for fmt in FORMATS:
            path = REPO / "samples" / "fixtures" / fmt / f"{stem}.{fmt}"
            if not path.exists():
                print(f"!! missing fixture {path}")
                mismatches += 1
                continue
            docs = [{"doc_id": "upload", "filename": path.name,
                     "content_b64": base64.b64encode(path.read_bytes()).decode()}]
            total += 1
            try:
                # Live LLM requested, no key present: must resolve without a call.
                state = run_pipeline(docs, f"CHK-{case_id}-{fmt}", llm="nvidia")
            except Exception as exc:  # noqa: BLE001
                mismatches += 1
                print(f"!! {stem}.{fmt}: {type(exc).__name__}: {exc}")
                continue
            source = (state.get("model_versions") or {}).get("extraction")
            got = _summary(state)
            if source != "structured-data":
                mismatches += 1
                print(f"!! {stem}.{fmt}: expected structured-data, got {source!r}")
            if got != want:
                mismatches += 1
                print(f"!! {stem}.{fmt}: dropdown {want} != upload {got}")

    print(f"\nchecked {total} uploads across {len(manifest['cases'])} cases x {len(FORMATS)} formats")
    print(f"mismatches: {mismatches}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
