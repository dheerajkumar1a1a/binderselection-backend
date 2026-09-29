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
    for doc in documents:
        hint = doc.get("structured_hint") or {}
        for field, raw in hint.items():
            if field == "total_insured_value":
                val, orig = _norm_money(raw)
            else:
                val, orig = raw, raw
            extracted[field] = val
            meta[field] = {
                "value": val,
                "original_value": orig,
                "present": True,
                "confidence": 1.0,
                "source_document_id": doc.get("doc_id"),
                "source_locator": "structured_hint",
            }
    for field in ("total_insured_value", "broker_name", "locations", "commodities"):
        if field not in extracted:
            extracted[field] = None
            meta[field] = {"present": False, "confidence": 0.0, "reason": "absent"}
    return extracted, meta


def extract(state: dict, llm=None) -> dict:
    documents = state.get("documents", [])
    if llm is not None:
        raise NotImplementedError("Live LLM path needs provider package + key; wire prompt->JSON here.")
    extracted, meta = stub_extract(documents)
    return {"extracted": extracted, "extracted_meta": meta}
