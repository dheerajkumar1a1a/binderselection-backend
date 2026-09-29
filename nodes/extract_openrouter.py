"""Live extraction via OpenRouter (https://openrouter.ai).

Env: OPENROUTER_API_KEY (required), OPENROUTER_MODEL (default below).
Uses stdlib urllib - no new dependencies. Free-tier default model;
override with any OpenRouter model id, e.g. google/gemini-2.0-flash-001.
Contract mirrors stub_extract: (extracted, meta) with provenance,
confidence, absent-stays-absent. Model output is validated, never trusted:
unknown fields dropped, missing fields marked absent, money normalised.
"""
import json
import os
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
FIELDS = ["total_insured_value", "broker_name", "locations", "commodities"]

PROMPT = """Extract marine-cargo submission fields from the documents below.
Return ONLY valid JSON, no markdown, with this shape:
{"fields": [{"name": "<one of: total_insured_value, broker_name, locations, commodities>",
"value": <JSON value or null if not stated>, "confidence": <0-1>,
"source_locator": "<quote or location, max 120 chars>"}]}
Rules: never invent values - use null when absent. Money as number when possible.
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
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://github.com/dheerajkumar1a1a/binderselection-backend",
                 "X-Title": "binderselection-backend extraction"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    content = payload["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(content)


def openrouter_extract(documents: list[dict], api_key: str | None = None,
                       model: str | None = None) -> tuple[dict, dict]:
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    model = model or DEFAULT_MODEL
    texts = [f"[{d.get('doc_id', '?')}:{d.get('filename', 'doc')}] {d.get('text', '')}"
             for d in documents]
    by_doc = {d.get("doc_id"): d for d in documents}
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
