"""Live extraction via OpenRouter (https://openrouter.ai).

Env: OPENROUTER_API_KEY (required), OPENROUTER_MODEL (default below).
Uses stdlib urllib - no new dependencies. Free-tier default model;
override with any OpenRouter model id, e.g. google/gemini-2.0-flash-001.
Contract mirrors stub_extract: (extracted, meta) with provenance,
confidence, absent-stays-absent. Model output is validated, never trusted:
unknown fields dropped, missing fields marked absent, money normalised.
"""
# json: parse request/response.
import json
# os: read env vars.
import os
# urllib.request: HTTP client.
import urllib.request

# OpenRouter chat completions endpoint.
API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Default model (free tier), overridable via env.
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
# Fields we accept from the model.
FIELDS = ["total_insured_value", "broker_name", "locations", "commodities"]

# PROMPT: instruction sent to the model.
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


# _call: make the HTTP request and parse the model response.
def _call(doc_texts: list[str], api_key: str, model: str) -> dict:
    # Build request body.
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT + "\n---\n".join(doc_texts)}],
        "temperature": 0,
    }).encode()
    # Build HTTP request with auth headers.
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/dheerajkumar1a1a/binderselection-backend",
                 "X-Title": "binderselection-backend extraction"})
    # Inner callable for retry.
    def _do():
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    # Retry on transient errors.
    from nodes.retry import with_retry
    payload = with_retry(_do)
    # Extract content string.
    content = payload["choices"][0]["message"]["content"].strip()
    # Strip markdown code fences if present.
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    # Parse JSON.
    return json.loads(content)


# openrouter_extract: public entry point.
def openrouter_extract(documents: list[dict], api_key: str | None = None,
                       model: str | None = None) -> tuple[dict, dict]:
    # Resolve API key from arg or env.
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    # Resolve model.
    model = model or DEFAULT_MODEL
    # Build text list from documents.
    texts = [f"[{d.get('doc_id', '?')}:{d.get('filename', 'doc')}] {d.get('text', '')}"
             for d in documents]
    raw = _call(texts, key, model)
    extracted: dict = {}
    meta: dict = {}
    # Process each returned field.
    for item in raw.get("fields", []):
        name = item.get("name")
        if name not in FIELDS:
            continue
        val = item.get("value")
        # Normalise money strings.
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
    # Mark absent fields.
    for f in FIELDS:
        if f not in extracted:
            extracted[f] = None
            meta[f] = {"present": False, "confidence": 0.0, "reason": "absent"}
    # Default source_document_id if missing.
    for m in meta.values():
        if not m.get("source_document_id") and documents:
            m.setdefault("source_document_id", (documents[0].get("doc_id")))
    return extracted, meta
