"""Rules console (phase 4): maker-checker proposals over versioned rulesets.

Lifecycle mechanics (proposal files, four-eyes, version numbering) live in
prod/maker_checker.py and are shared with the capacity console. This module
supplies only what is specific to rules: validation, the version document
shape, and rule-level diffing.

Reuses rules/store.py (validate_rule, load_effective, dry_run) rather than
duplicating engine logic. Approval writes the next versioned ruleset file
binder_<id>_v<N>.json with the chosen effective_from; the engine
(load_effective) picks the right version by effective date at run time.
"""
from __future__ import annotations

# json: read seed/sample files for dry-run.
import json
# os: paths.
import os
# sys: make the repo importable when run as a script.
import sys as _sys
from pathlib import Path

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rules import store as rules_store
from prod import maker_checker as mc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS_DIR = os.path.join(ROOT, "rules")
PROPOSALS_DIR = os.path.join(ROOT, "rules", "proposals")
BINDERS_PATH = os.path.join(ROOT, "rules", "binders.json")


def _binder_ids() -> list[str]:
    data = json.load(open(BINDERS_PATH, encoding="utf-8"))
    return [b["binder_id"] for b in data.get("binders", [])]


def list_binders() -> list[dict]:
    data = json.load(open(BINDERS_PATH, encoding="utf-8"))
    out = []
    for b in data.get("binders", []):
        bid = b["binder_id"]
        versions = []
        for entry in mc.list_versions(VERSIONS_DIR, bid):
            d = entry["data"]
            versions.append({"file": entry["file"],
                             "version": d.get("version"),
                             "effective_from": d.get("effective_from"),
                             "effective_to": d.get("effective_to"),
                             "author": d.get("author"),
                             "approver": d.get("approver"),
                             "rules": len(d.get("rules", []))})
        try:
            cur = rules_store.load_effective(bid)
            current = {"version": cur.get("version"),
                       "effective_from": cur.get("effective_from")}
        except FileNotFoundError:
            current = None
        out.append({"binder": b, "versions": versions, "current": current})
    return out


def _current_ruleset(binder_id: str) -> dict:
    return rules_store.load_effective(binder_id)


RULE_TEMPLATES = {
    "tiv_ceiling": {"rule_id": "NEW-TIV-CEILING", "category": "Total Insured Value",
                    "scope": "submission", "field_reference": "total_insured_value",
                    "operator": "lte", "threshold_value": 10000000, "threshold_unit": "currency",
                    "severity": "refer", "business_description": "If TIV exceeds the ceiling"},
    "territory_restriction": {"rule_id": "NEW-TERRITORY", "category": "Territory",
                             "scope": "location", "field_reference": "locations.territory",
                             "operator": "not_in", "threshold_value": ["CA", "TX"],
                             "threshold_unit": "list", "severity": "decline",
                             "business_description": "Decline risks in restricted territories"},
    "loss_history": {"rule_id": "NEW-LOSS-HISTORY", "category": "Loss History",
                     "scope": "submission", "field_reference": "largest_single_claim_amount",
                     "operator": "lt", "threshold_value": 5000, "threshold_unit": "currency",
                     "severity": "refer", "business_description": "If largest single claim exceeds threshold"},
    "capacity_check": {"rule_id": "NEW-CAPACITY", "category": "Capacity",
                       "scope": "submission", "field_reference": "total_insured_value",
                       "operator": "lte", "threshold_value": 5000000, "threshold_unit": "currency",
                       "severity": "refer", "business_description": "Capacity-based TIV limit"},
}


def list_proposals() -> list[dict]:
    return mc.list_proposals(PROPOSALS_DIR)


def get_proposal(proposal_id: str) -> dict | None:
    return mc.get_proposal(PROPOSALS_DIR, proposal_id)


def create_proposal(binder_id: str, ruleset: dict, author: str,
                    effective_from: str, summary: str = "") -> dict:
    if binder_id not in _binder_ids():
        raise ValueError(f"unknown binder {binder_id}")
    # Validate every rule before it can be proposed.
    errs = []
    for r in ruleset.get("rules", []):
        errs.extend(rules_store.validate_rule(r))
    if errs:
        raise ValueError("invalid rules: " + "; ".join(errs))
    return mc.create_proposal(PROPOSALS_DIR, binder_id, ruleset, author,
                              effective_from, summary, payload_key="ruleset")


def dry_run_proposal(binder_id: str, proposed: dict, case_ids: list[str]) -> dict:
    try:
        current = rules_store.load_effective(binder_id)
    except FileNotFoundError:
        current = {"rules": []}
    # Load sample cases from disk.
    cases = []
    for cid in case_ids:
        path = os.path.join(ROOT, "docs", "data", "samples", "cases", cid + ".json")
        if os.path.exists(path):
            raw = json.load(open(path, encoding="utf-8"))
            # The engine expects the parsed document list; sample docs carry
            # structured_hint/text already, so hand them through as-is.
            cases.append({"documents": raw.get("documents", [])})
    return rules_store.dry_run(cases, current, proposed)


def _build_version(proposal: dict, version: int, supersedes: int | None,
                   approver: str) -> dict:
    ruleset = dict(proposal["ruleset"])
    ruleset["binder_id"] = proposal["binder_id"]
    ruleset["version"] = version
    ruleset["effective_from"] = proposal["effective_from"]
    ruleset["effective_to"] = None
    ruleset["supersedes"] = supersedes
    ruleset["author"] = proposal["author"]
    ruleset["approver"] = approver
    return ruleset


def approve_proposal(proposal_id: str, approver: str) -> dict:
    return mc.approve(PROPOSALS_DIR, VERSIONS_DIR, proposal_id, approver,
                      _build_version, payload_key="ruleset")


def rollback_proposal(binder_id: str, target_version: int, author: str,
                      effective_from: str, summary: str = "") -> dict:
    """Create a proposal that reverts to a previous version's ruleset."""
    old_ruleset = mc.load_version(VERSIONS_DIR, binder_id, target_version)
    ruleset = {"binder_id": binder_id, "rules": old_ruleset.get("rules", [])}
    return create_proposal(binder_id, ruleset, author, effective_from,
                           summary or f"Rollback to v{target_version}")


def diff_versions(binder_id: str, v1: int, v2: int) -> dict:
    """Diff two versions of a binder's ruleset."""
    d1 = mc.load_version(VERSIONS_DIR, binder_id, v1)
    d2 = mc.load_version(VERSIONS_DIR, binder_id, v2)
    r1 = {r["rule_id"]: r for r in d1.get("rules", [])}
    r2 = {r["rule_id"]: r for r in d2.get("rules", [])}
    added = [r2[rid] for rid in r2 if rid not in r1]
    removed = [r1[rid] for rid in r1 if rid not in r2]
    changed = []
    for rid in r1:
        if rid in r2 and r1[rid] != r2[rid]:
            changed.append({"rule_id": rid, "before": r1[rid], "after": r2[rid]})
    return {"v1": v1, "v2": v2, "added": added, "removed": removed,
            "changed": changed,
            "unchanged": len([r for r in r1 if r in r2 and r1[r] == r2[r]])}
