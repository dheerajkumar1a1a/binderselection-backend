"""Live extraction via OpenRouter (https://openrouter.ai).

Env: OPENROUTER_API_KEY (required), OPENROUTER_MODEL (default below).
Uses stdlib urllib - no new dependencies. Free-tier default model;
override with any OpenRouter model id, e.g. google/gemini-2.0-flash-001.
Contract mirrors stub_extract: (extracted, meta) with provenance,
confidence, absent-stays-absent. Model output is validated, never trusted:
unknown fields dropped, missing fields marked absent, money normalised.
Extracts the full 13-field schema (matches the NVIDIA provider) so that
real submissions can be evaluated end-to-end, not just 4 fields.
"""
import json
import os
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
FIELDS = ["total_insured_value", "broker_name", "locations", "commodities",
          "coverage_sections", "valuation_basis", "coverage_type",
          "requested_inception_date", "expiring_premium_disclosed",
          "insured_state_province", "insured_country",
          "largest_single_claim_amount", "total_claims_amount"]

PROMPT = """Extract marine-cargo submission fields from the documents below.
Return ONLY valid JSON, no markdown, with this shape:
{"fields": [
 {"name": "total_insured_value", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote, max 120 chars>"},
 {"name": "broker_name", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "locations", "value": [{"address": "<string>", "sprinklered": <true/false/null>}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "commodities", "value": [{"commodity_type": "<UPPER_SNAKE string>"}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "coverage_sections", "value": [{"limit": <number>}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "valuation_basis", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "coverage_type", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "requested_inception_date", "value": "<YYYY-MM-DD or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "expiring_premium_disclosed", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "insured_state_province", "value": "<2-letter code or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "insured_country", "value": "<2-letter code or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "largest_single_claim_amount", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "total_claims_amount", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"}
]}
Rules: return exactly one entry per name, in the listed order, using null
where the documents do not state it. Never invent values. Money as numbers.
Locations MUST be a list of objects (empty list if none stated).
Commodities MUST be a list of objects. "No claims" means 0 amounts.
"Not disclosed" means false for expiring_premium_disclosed.
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
    def _do():
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    from nodes.retry import with_retry
    payload = with_retry(_do)
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
    raw = _call(texts, key, model)
    extracted: dict = {}
    meta: dict = {}
    for item in raw.get("fields", []):
        name = item.get("name")
        if name not in FIELDS:
            continue
        val = item.get("value")
        if name in ("total_insured_value", "largest_single_claim_amount",
                    "total_claims_amount") and isinstance(val, str):
            try:
                val = float(val.replace("$", "").replace(",", "").strip())
            except ValueError:
                val = None
        if name == "coverage_sections" and isinstance(val, list):
            fixed = []
            for s in val:
                if isinstance(s, dict) and "limit" in s:
                    lim = s["limit"]
                    if isinstance(lim, str):
                        try:
                            lim = float(lim.replace("$", "").replace(",", "").strip())
                        except ValueError:
                            lim = None
                    fixed.append({"limit": lim})
            val = fixed
        if name == "expiring_premium_disclosed" and isinstance(val, str):
            low = val.lower()
            val = ("true" in low or "yes" in low or "disclosed" in low) \
                and "not disclosed" not in low and "undisclosed" not in low \
                and not low.startswith("no ")
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
