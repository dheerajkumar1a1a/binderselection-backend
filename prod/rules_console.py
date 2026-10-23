"""Rules console (phase 4): maker-checker proposals over versioned rulesets.

Reuses rules/store.py (validate_rule, load_effective, propose, approve, dry_run)
rather than duplicating engine logic. Proposals are JSON files under
rules/proposals/ (draft -> approved); approval writes the next versioned
ruleset file binder_<id>_v<N>.json with the chosen effective_from. The
engine (load_effective) picks the right version by effective date at run
time, so a proposal's effect is automatic once approved.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime

from . import auth
from .. import rules as _rules_pkg  # noqa: F401
import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from rules import store as rules_store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPOSALS_DIR = os.path.join(ROOT, "rules", "proposals")
BINDERS_PATH = os.path.join(ROOT, "rules", "binders.json")


def _ensure_dir():
    os.makedirs(PROPOSALS_DIR, exist_ok=True)


def _binder_ids() -> list[str]:
    data = json.load(open(BINDERS_PATH, encoding="utf-8"))
    return [b["binder_id"] for b in data.get("binders", [])]


def list_binders() -> list[dict]:
    data = json.load(open(BINDERS_PATH, encoding="utf-8"))
    out = []
    for b in data.get("binders", []):
        bid = b["binder_id"]
        versions = []
        import glob as _g
        for p in sorted(_g.glob(os.path.join(ROOT, "rules", f"{bid}_v*.json"))):
            d = json.load(open(p, encoding="utf-8"))
            versions.append({"file": os.path.basename(p),
                            "version": d.get("version"), "effective_from": d.get("effective_from"),
                            "effective_to": d.get("effective_to"),
                            "author": d.get("author"), "approver": d.get("approver"),
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
    _ensure_dir()
    out = []
    for fn in sorted(os.listdir(PROPOSALS_DIR)):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(PROPOSALS_DIR, fn), encoding="utf-8"))
        d["_file"] = fn
        out.append(d)
    return out


def get_proposal(proposal_id: str) -> dict | None:
    _ensure_dir()
    path = os.path.join(PROPOSALS_DIR, proposal_id + ".json")
    if not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    d["_file"] = proposal_id + ".json"
    return d


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
    if not effective_from:
        raise ValueError("effective_from is required")
    # four-eyes is enforced at approval time; authoring is open to any
    # underwriter/admin (Q1).
    proposal_id = "P-" + uuid.uuid4().hex[:8]
    proposal = {"proposal_id": proposal_id, "binder_id": binder_id,
                "status": "draft", "author": author, "approver": None,
                "effective_from": effective_from, "summary": summary,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "ruleset": ruleset, "approved_version": None}
    _ensure_dir()
    with open(os.path.join(PROPOSALS_DIR, proposal_id + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)
    return proposal


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


def approve_proposal(proposal_id: str, approver: str) -> dict:
    proposal = get_proposal(proposal_id)
    if proposal is None:
        raise ValueError("proposal not found")
    if proposal.get("status") != "draft":
        raise ValueError("proposal is not in draft state")
    if approver == proposal.get("author"):
        raise ValueError("four-eyes: approver must differ from author")
    # Write the next versioned ruleset file.
    binder_id = proposal["binder_id"]
    existing = []
    import glob as _g
    for p in _g.glob(os.path.join(ROOT, "rules", f"{binder_id}_v*.json")):
        existing.append(int(p.rsplit("_v", 1)[1].split(".json")[0]))
    next_ver = (max(existing) if existing else 0) + 1
    ruleset = dict(proposal["ruleset"])
    ruleset["binder_id"] = binder_id
    ruleset["version"] = next_ver
    ruleset["effective_from"] = proposal["effective_from"]
    ruleset["effective_to"] = None
    ruleset["supersedes"] = (max(existing) if existing else None)
    ruleset["author"] = proposal["author"]
    ruleset["approver"] = approver
    out_path = os.path.join(ROOT, "rules", f"{binder_id}_v{next_ver}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ruleset, f, indent=2)
    proposal["status"] = "approved"
    proposal["approver"] = approver
    proposal["approved_version"] = next_ver
    proposal["approved_at"] = datetime.now().isoformat(timespec="seconds")
    with open(os.path.join(PROPOSALS_DIR, proposal_id + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(proposal, f, indent=2)
    return proposal
