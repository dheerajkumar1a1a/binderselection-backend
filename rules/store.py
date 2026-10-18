"""Rule administration: versioned reference data, four-eyes, dry-run (BFR-ADM).

Layout: rules/binder_<id>_v<version>.json (approved), proposals/ (drafts).
"""
# json: parse rulesets.
import json
# date: effective-date filtering.
from datetime import date
# Path: filesystem paths.
from pathlib import Path

# BASE: rules directory.
BASE = Path(__file__).resolve().parent
# KNOWN_FIELDS: valid field references for rules.
KNOWN_FIELDS = {
    "total_insured_value", "broker_name", "locations", "commodities",
    "locations.sprinklered", "commodities.commodity_type",
    "broker_count", "policy_term_months",
    "coverage_sections.limit", "largest_single_claim_amount",
    "total_claims_amount", "claim_count_3_years", "claim_count_5_years",
    "losses", "insured_in_continental_us", "insured_country",
    "insured_state_province", "valuation_basis", "coverage_type",
    "requested_inception_date", "expiring_premium_disclosed",
    "business_commencement_date", "years_trading",
    "locations.territory", "locations.wildfire_risk_score",
    "locations.fema_flood_zone", "locations.construction_type",
    "locations.alarm_present", "locations.year_built",
    "prior_coverage_cancelled", "prior_coverage_non_renewed",
    "profit_share_requested", "no_claims_bonus_requested",
    "locations.country", "locations.alarm_type", "locations.location_limit",
    "locations.roofing_type", "locations.cctv_present",
    "locations.cope_details_complete", "locations.flood_tier",
    "location_count", "valuation_basis_stated_clearly",
    "sov_complete", "deductible_options_count",
    "prior_cargo_coverage_cancelled", "loss_run_provided",
    "insured_postcode_zip",
}
# VALID_OPS: allowed operators.
VALID_OPS = {"lte", "lt", "gte", "gt", "eq", "neq", "in", "not_in",
             "is_true", "is_false", "is_absent", "is_present",
             "before", "after"}


# validate_rule: validate a single rule dict.
def validate_rule(rule: dict) -> list[str]:
    errors = []
    if rule.get("field_reference") not in KNOWN_FIELDS:
        errors.append(f"unknown field: {rule.get('field_reference')}")
    if rule.get("operator") not in VALID_OPS:
        errors.append(f"invalid operator: {rule.get('operator')}")
    if "threshold_unit" not in rule:
        errors.append("threshold_unit required")
    return errors


# _binder_files: list versioned ruleset files for a binder.
def _binder_files(binder_id: str) -> list[Path]:
    return sorted(BASE.glob(f"{binder_id}_v*.json"))


# load_effective: load the effective ruleset for a binder as of a date.
def load_effective(binder_id: str, as_at: str | None = None) -> dict:
    as_at = as_at or date.today().isoformat()
    best = None
    for p in _binder_files(binder_id):
        data = json.loads(p.read_text())
        if data.get("effective_from", "") <= as_at and (data.get("effective_to") is None or data["effective_to"] >= as_at):
            if best is None or data.get("version", 0) > best.get("version", 0):
                best = data
    if best is None:
        raise FileNotFoundError(f"no effective ruleset for {binder_id} at {as_at}")
    return best


# is_active: check binder lifecycle status.
def is_active(binder_id: str, as_at: str | None = None,
              registry: list[dict] | None = None) -> bool:
    as_at = as_at or date.today().isoformat()
    reg = registry if registry is not None else json.loads((BASE / "binders.json").read_text())["binders"]
    for b in reg:
        if b["binder_id"] == binder_id:
            in_range = b.get("effective_from", "") <= as_at and (b.get("effective_to") is None or b["effective_to"] >= as_at)
            return b.get("status") == "active" and in_range
    return False


# propose: create a draft proposal (author only).
def propose(ruleset: dict, author: str) -> dict:
    return {"status": "draft", "author": author, "approver": None, "ruleset": ruleset}


# approve: four-eyes approval (approver != author).
def approve(proposal: dict, approver: str) -> dict:
    if approver == proposal.get("author"):
        raise ValueError("four-eyes: approver must differ from author")
    proposal["approver"] = approver
    proposal["status"] = "approved"
    return proposal


# dry_run: evaluate proposed vs current ruleset on sample cases.
def dry_run(cases: list[dict], current: dict, proposed: dict) -> dict:
    import sys
    sys.path.insert(0, str(BASE.parent))
    from nodes.appetite import evaluate_rule
    changed = []
    for i, case in enumerate(cases):
        before = [evaluate_rule(case, r) for r in current["rules"]]
        after = [evaluate_rule(case, r) for r in proposed["rules"]]
        b = "Decline" if any(o["outcome"] == "Decline" for o in before) else "Accept"
        a = "Decline" if any(o["outcome"] == "Decline" for o in after) else "Accept"
        if b != a:
            changed.append({"case": i, "before": b, "after": a})
    return {"total": len(cases), "changed": len(changed), "details": changed}
