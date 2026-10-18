"""LLM extraction node: reads documents, never decides (BFR 3.3, BFR-EXT).

Envelope per field (7.1.7 subset): value, original_value, present,
confidence, source_document_id, source_locator.
Absent fields stay absent - no inference (BFR-EXT-003).
Currency normalised, original kept (BFR-EXT-008).
Stub extractor runs without keys; pass a LangChain chat model for live use.
"""
# Any: type hint for arbitrary values.
from typing import Any


# _norm_money: normalise money to float, keeping original.
def _norm_money(raw: Any) -> tuple[Any, Any]:
    if isinstance(raw, (int, float)):
        return float(raw), raw
    if isinstance(raw, str):
        orig = raw
        try:
            return float(raw.replace("$", "").replace(",", "").strip()), orig
        except ValueError:
            return None, orig
    return None, raw


# stub_extract: deterministic extraction from structured hints.
def stub_extract(documents: list[dict]) -> tuple[dict, dict]:
    extracted: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    seen: dict[str, list] = {}
    for doc in documents:
        hint = doc.get("structured_hint") or {}
        for field, raw in hint.items():
            if field == "total_insured_value":
                val, orig = _norm_money(raw)
            else:
                val, orig = raw, raw
            # Track sightings for conflict detection.
            seen.setdefault(field, []).append(
                {"value": val, "source_document_id": doc.get("doc_id")})
            if field not in extracted:
                extracted[field] = val
                meta[field] = {
                    "value": val,
                    "original_value": orig,
                    "present": True,
                    "confidence": 1.0,
                    "source_document_id": doc.get("doc_id"),
                    "source_locator": "structured_hint",
                }
    # Mark contested fields where sources disagree.
    for field, sightings in seen.items():
        distinct = {json_dumps(s["value"]) for s in sightings}
        if len(distinct) > 1:
            meta[field]["contested"] = True
            meta[field]["conflict"] = sightings
    # Ensure mandatory fields are present or marked absent.
    for field in ("total_insured_value", "broker_name", "locations", "commodities"):
        if field not in extracted:
            extracted[field] = None
            meta[field] = {"present": False, "confidence": 0.0, "reason": "absent"}
    return extracted, meta


# json_dumps: stable JSON serialisation for value comparison.
def json_dumps(v: Any) -> str:
    import json as _json
    return _json.dumps(v, sort_keys=True, default=str)


# extract: graph node entry point; routes to provider or stub.
def extract(state: dict, llm=None) -> dict:
    documents = state.get("documents", [])
    # OpenRouter live extraction.
    if llm == "openrouter":
        from nodes.extract_openrouter import openrouter_extract, DEFAULT_MODEL
        extracted, meta = openrouter_extract(documents)
        return {"extracted": extracted, "extracted_meta": meta,
                "model_versions": {"extraction": DEFAULT_MODEL, "narrative": None}}
    # NVIDIA live extraction.
    if llm == "nvidia":
        from nodes.extract_nvidia import nvidia_extract, DEFAULT_MODEL as NV_MODEL
        extracted, meta = nvidia_extract(documents)
        return {"extracted": extracted, "extracted_meta": meta,
                "model_versions": {"extraction": NV_MODEL, "narrative": None}}
    # Unknown option → error.
    if llm is not None:
        raise NotImplementedError("Unknown llm option; use llm='nvidia', 'openrouter' or None (stub).")
    # Default: stub extraction.
    extracted, meta = stub_extract(documents)
    return {"extracted": extracted, "extracted_meta": meta,
            "model_versions": {"extraction": "stub-1", "narrative": None}}
