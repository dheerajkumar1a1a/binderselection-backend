"""Live extraction via Google Gemini (Generative Language API).

Env: GEMINI_API_KEY, or GEMINI_API_KEY_FILE (path to a file holding the key -
preferred, so the key is never exported into a shell or committed).
     GEMINI_MODEL (override; default below).
Default: gemini-3.5-flash-lite (verified on the account).
Stdlib only - no new dependencies. Same validated envelope as the other
providers: unknown fields dropped, absent stays absent, money normalised.
The model reads; it never decides.
"""
# json: parse request/response.
import json
# os: read env vars.
import os
# urllib.request: HTTP client.
import urllib.request

# Gemini generateContent endpoint (model + key substituted at call time).
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
# Default model, overridable via env.
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Fields accepted from the model (30-field schema).
FIELDS = ["total_insured_value", "broker_name", "locations", "commodities",
          "coverage_sections", "valuation_basis", "coverage_type",
          "requested_inception_date", "expiring_premium_disclosed",
          "insured_state_province", "insured_country",
          "largest_single_claim_amount", "total_claims_amount",
          "prior_coverage_cancelled", "prior_coverage_non_renewed",
          "profit_share_requested", "no_claims_bonus_requested",
          "years_trading", "business_commencement_date",
          "claim_count_3_years", "claim_count_5_years",
          "insured_in_continental_us", "policy_term_months",
          "valuation_basis_stated_clearly", "broker_count",
          "sov_complete", "deductible_options_count",
          "insured_postcode_zip", "loss_run_provided", "prior_cargo_coverage_cancelled"]

# PROMPT: instruction sent to the model (full 30-field schema).
PROMPT = """Extract marine-cargo submission fields from the documents below.
Return ONLY valid JSON, no markdown, with this shape:
{"fields": [
 {"name": "total_insured_value", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote, max 120 chars>"},
 {"name": "broker_name", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "locations", "value": [{"address": "<string>", "sprinklered": <true/false/null>, "territory": "<2-letter or null>", "wildfire_risk_score": <number or null>, "fema_flood_zone": "<string or null>", "construction_type": "<string or null>", "alarm_present": <true/false/null>, "year_built": <number or null>, "alarm_type": "<string or null>", "country": "<2-letter or null>", "location_limit": <number or null>, "flood_tier": "<string or null>", "roofing_type": "<string or null>", "cctv_present": <true/false/null>, "cope_details_complete": <true/false/null>}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "commodities", "value": [{"commodity_type": "<UPPER_SNAKE string>"}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "coverage_sections", "value": [{"limit": <number>}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "valuation_basis", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "coverage_type", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "requested_inception_date", "value": "<YYYY-MM-DD or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "expiring_premium_disclosed", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "insured_state_province", "value": "<2-letter code or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "insured_country", "value": "<2-letter code or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "largest_single_claim_amount", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "total_claims_amount", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "prior_coverage_cancelled", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "prior_coverage_non_renewed", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "profit_share_requested", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "no_claims_bonus_requested", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "years_trading", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "business_commencement_date", "value": "<YYYY-MM-DD or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "claim_count_3_years", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "claim_count_5_years", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "insured_in_continental_us", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "policy_term_months", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "valuation_basis_stated_clearly", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "broker_count", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "sov_complete", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "deductible_options_count", "value": <number or null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "insured_postcode_zip", "value": "<string or null>", "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "loss_run_provided", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"},
 {"name": "prior_cargo_coverage_cancelled", "value": <true/false/null>, "confidence": <0-1>, "source_locator": "<quote>"}
]}
Rules: return exactly one entry per name, in the listed order, using null
where the documents do not state it. Never invent values. Money as numbers.
Locations MUST be a list of objects (empty list if none stated).
Commodities MUST be a list of objects. "No claims" means 0 amounts.
"Not disclosed" means false for expiring_premium_disclosed.
Documents:
"""


# _api_key: resolve the Gemini key from env or a read-only key file.
# Never log or return the raw path contents; the key is used, not stored.
def _api_key(api_key: str | None = None) -> str:
    # Explicit argument wins (tests, callers).
    if api_key:
        return api_key
    # Env var first.
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    # Otherwise read from the file named by GEMINI_API_KEY_FILE.
    path = os.environ.get("GEMINI_API_KEY_FILE")
    if path:
        try:
            return open(path, encoding="utf-8").read().strip()
        except OSError as e:
            raise RuntimeError(f"GEMINI_API_KEY_FILE unreadable: {e}") from e
    raise RuntimeError("GEMINI_API_KEY not set (set GEMINI_API_KEY or GEMINI_API_KEY_FILE)")


# _call: POST to generateContent and return the parsed JSON object.
def _call(doc_texts: list[str], api_key: str, model: str) -> dict:
    # URL carries the key as a query param (Google's documented scheme).
    url = f"{API_BASE}/{model}:generateContent?key={api_key}"
    # Request body: one user turn holding the prompt + documents.
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": PROMPT + "\n---\n".join(doc_texts)}]}],
        # temperature 0 for repeatability; force a JSON body (no markdown).
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    # Build the request.
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"})
    # Retry wrapper for transient errors.
    from nodes.retry import with_retry

    # Inner callable for retry.
    def _do():
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    # Retry on transient errors.
    payload = with_retry(_do)
    # A blocked/empty response has no candidates - fail loudly, never guess.
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(payload)[:200]}")
    # Join all text parts (thinking models may emit separate parts).
    parts = (candidates[0].get("content") or {}).get("parts") or []
    content = "".join(p.get("text", "") for p in parts).strip()
    # Strip code fences if the model ignored the JSON mode.
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    # Parse the fields object.
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Gemini occasionally appends prose after the object ("Extra data").
        # Take the first complete object instead of failing the whole evaluation.
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(content[start:end + 1])


# _fields_of: accept either {"fields": [...]} or a bare list of field objects.
# Gemini's JSON mode does not guarantee the wrapper key, and a shape mismatch
# must not lose the whole extraction.
def _fields_of(raw) -> list:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        fields = raw.get("fields")
        if isinstance(fields, list):
            return [x for x in fields if isinstance(x, dict)]
    return []


# gemini_extract: public entry point; returns (extracted, meta).
def gemini_extract(documents: list[dict], api_key: str | None = None,
                   model: str | None = None) -> tuple[dict, dict]:
    # Resolve API key (arg -> env -> key file).
    key = _api_key(api_key)
    # Resolve model.
    model = model or DEFAULT_MODEL
    # Build text list with a source label per document.
    texts = [f"[{d.get('doc_id', '?')}:{d.get('filename', 'doc')}] {d.get('text', '')}"
             for d in documents]
    raw = _call(texts, key, model)
    extracted: dict = {}
    meta: dict = {}
    # Process each returned field.
    for item in _fields_of(raw):
        name = item.get("name")
        # Drop anything outside the schema (anti-hallucination).
        if name not in FIELDS:
            continue
        val = item.get("value")
        # Normalise money strings for money fields.
        if name in ("total_insured_value", "largest_single_claim_amount",
                    "total_claims_amount") and isinstance(val, str):
            try:
                val = float(val.replace("$", "").replace(",", "").strip())
            except ValueError:
                val = None
        # Normalise coverage_sections limits.
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
        # Normalise expiring_premium_disclosed from string.
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
    # Mark absent fields.
    for f in FIELDS:
        if f not in extracted:
            extracted[f] = None
            meta[f] = {"present": False, "confidence": 0.0, "reason": "absent"}
    # Default source_document_id if the model omitted it (None counts as
    # omitted - the key existing is not enough).
    for m in meta.values():
        if not m.get("source_document_id") and documents:
            m["source_document_id"] = documents[0].get("doc_id")
        if "sources" not in m:
            m["sources"] = [{"source_document_id": m.get("source_document_id"),
                            "value": m.get("value")}] if m.get("present") else []
    return extracted, meta
