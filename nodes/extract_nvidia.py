"""Live extraction via NVIDIA API (OpenAI-compatible, Nemotron).

Env: NVIDIA_API_KEY (required, never committed), NVIDIA_MODEL (override).
Default: nvidia/nemotron-3-super-120b-a12b (120B, verified on the account).
Stdlib only - no new dependencies. Same validated envelope as the
OpenRouter provider: unknown fields dropped, absent stays absent,
money normalised. The model reads; it never decides.
"""
# json: parse request/response.
import json
# os: read env vars.
import os
# urllib.request: HTTP client.
import urllib.request

# NVIDIA chat completions endpoint.
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Default model, overridable via env.
DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
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
 {"name": "locations", "value": [{"address": "<string>", "sprinklered": <true/false/null>, "territory": "<2-letter or null>", "wildfire_risk_score": <number or null>, "fema_flood_zone": "<string or null>", "construction_type": "<string or null>", "alarm_present": <true/false/null>, "year_built": <number or null>}] or null, "confidence": <0-1>, "source_locator": "<quote>"},
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


# _call: make the HTTP request and parse the model response.
def _call(doc_texts: list[str], api_key: str, model: str) -> dict:
    # Build request body.
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT + "\n---\n".join(doc_texts)}],
        "temperature": 0,
    }).encode()
    # Build HTTP request with auth header.
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"})
    # Retry import.
    from nodes.retry import with_retry

    # Inner callable for retry.
    def _do():
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    # Retry on transient errors.
    payload = with_retry(_do)
    # Extract content.
    content = payload["choices"][0]["message"]["content"].strip()
    # Strip code fences.
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    # Parse JSON.
    return json.loads(content)


# nvidia_extract: public entry point.
def nvidia_extract(documents: list[dict], api_key: str | None = None,
                   model: str | None = None) -> tuple[dict, dict]:
    # Resolve API key.
    key = api_key or os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY not set")
    # Resolve model.
    model = model or DEFAULT_MODEL
    # Build text list.
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
    # Default source_document_id if missing.
    for m in meta.values():
        if not m.get("source_document_id") and documents:
            m.setdefault("source_document_id", (documents[0].get("doc_id")))
    return extracted, meta
