"""LLM extraction node: reads documents, never decides (BFR 3.3, BFR-EXT).

Envelope per field (7.1.7 subset): value, original_value, present,
confidence, source_document_id, source_locator.
Absent fields stay absent - no inference (BFR-EXT-003).
Currency normalised, original kept (BFR-EXT-008).
Stub extractor runs without keys; pass a LangChain chat model for live use.
"""
from typing import Any


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
    for field, sightings in seen.items():
        distinct = {json_dumps(s["value"]) for s in sightings}
        if len(distinct) > 1:
            meta[field]["contested"] = True
            meta[field]["conflict"] = sightings
    for field in ("total_insured_value", "broker_name", "locations", "commodities"):
        if field not in extracted:
            extracted[field] = None
            meta[field] = {"present": False, "confidence": 0.0, "reason": "absent"}
    return extracted, meta


def json_dumps(v: Any) -> str:
    import json as _json
    return _json.dumps(v, sort_keys=True, default=str)


def extract(state: dict, llm=None) -> dict:
    documents = state.get("documents", [])
    if llm == "openrouter":
        from nodes.extract_openrouter import openrouter_extract, DEFAULT_MODEL
        extracted, meta = openrouter_extract(documents)
        return {"extracted": extracted, "extracted_meta": meta,
                "model_versions": {"extraction": DEFAULT_MODEL, "narrative": None}}
    if llm == "nvidia":
        from nodes.extract_nvidia import nvidia_extract, DEFAULT_MODEL as NV_MODEL
        extracted, meta = nvidia_extract(documents)
        return {"extracted": extracted, "extracted_meta": meta,
                "model_versions": {"extraction": NV_MODEL, "narrative": None}}
    if llm is not None:
        raise NotImplementedError("Unknown llm option; use llm='nvidia', 'openrouter' or None (stub).")
    extracted, meta = stub_extract(documents)
    return {"extracted": extracted, "extracted_meta": meta,
            "model_versions": {"extraction": "stub-1", "narrative": None}}
