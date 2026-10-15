"""Live extraction via NVIDIA API (OpenAI-compatible, Nemotron).

Env: NVIDIA_API_KEY (required, never committed), NVIDIA_MODEL (override).
Default: nvidia/nemotron-3-super-120b-a12b (120B, verified on the account).
Stdlib only - no new dependencies. Same validated envelope as the
OpenRouter provider: unknown fields dropped, absent stays absent,
money normalised. The model reads; it never decides.
"""
import json
import os
import urllib.request

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
FIELDS = ["total_insured_value", "broker_name", "locations", "commodities"]

PROMPT = """Extract marine-cargo submission fields from the documents below.
Return ONLY valid JSON, no markdown, with this shape:
{"fields": [
 {"name": "total_insured_value", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote, max 120 chars>"},
 {"name": "broker_name", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "locations", "value": [{"address": "<string>", "sprinklered": <true/false/null>}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "commodities", "value": [{"commodity_type": "<UPPER_SNAKE string>"}] or null, "confidence": <0-1>, "source_locator": "<quote>"}
]}
Rules: never invent values - use null when absent. Money as number when possible.
locations MUST be a list of objects (empty list if none stated). commodities MUST be a list of objects.
Documents:
"""


def _call(doc_texts: list[str], api_key: str, model: str) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT + "\n---\n".join(doc_texts)}],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"})
    from nodes.retry import with_retry

    def _do():
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    payload = with_retry(_do)
    content = payload["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(content)


def nvidia_extract(documents: list[dict], api_key: str | None = None,
                   model: str | None = None) -> tuple[dict, dict]:
    key = api_key or os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY not set")
    model = model or DEFAULT_MODEL
    texts = [f"[{d.get('doc_id', '?')}:{d.get('filename', 'doc')}] {d.get('text', '')}"
             for d in documents]
    raw = _call(texts, key, model)
    extracted: dict = {}
    meta: dict = {}
    for item in raw.get("fields", []):
        name = item.get("name")
        if name not in FIELDS:
            continue
        val = item.get("value")
        if name == "total_insured_value" and isinstance(val, str):
            try:
                val = float(val.replace("$", "").replace(",", "").strip())
            except ValueError:
                val = None
        extracted[name] = val
        meta[name] = {"value": val, "original_value": item.get("value"),
                      "present": val is not None,
                      "confidence": float(item.get("confidence", 0.5)),
                      "source_document_id": item.get("source_document_id"),
                      "source_locator": (item.get("source_locator") or "")[:120],
                      "model": model}
    for f in FIELDS:
        if f not in extracted:
            extracted[f] = None
            meta[f] = {"present": False, "confidence": 0.0, "reason": "absent"}
    for m in meta.values():
        if not m.get("source_document_id") and documents:
            m.setdefault("source_document_id", (documents[0].get("doc_id")))
    return extracted, meta
