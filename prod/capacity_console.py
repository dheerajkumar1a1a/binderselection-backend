"""Capacity console: maker-checker proposals over versioned authorised lines.

Lifecycle mechanics live in prod/maker_checker.py (shared with the rules
console). This module supplies what is specific to capacity: validation of a
single currency figure, the version document shape, scalar diffing, and a
dry-run that shows which sample cases flip eligibility (ADR-0002).
"""
from __future__ import annotations

# json: sample case files for dry-run.
import json
# os: paths.
import os
# sys: repo import.
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from capacity import store as capstore
from capacity import ledger as ledger_mod
from prod import maker_checker as mc

VERSIONS_DIR = str(capstore.VERSIONS_DIR)
PROPOSALS_DIR = str(capstore.PROPOSALS_DIR)
CASE_DIR = os.path.join(ROOT, "docs", "data", "samples", "cases")


# _registry: binder registry entries.
def _registry() -> list[dict]:
    return capstore._binders()


# _binder_ids: known binder ids.
def _binder_ids() -> list[str]:
    return [b["binder_id"] for b in _registry() if b.get("binder_id")]


# list_binders: registry plus version history plus the effective version.
def list_binders() -> list[dict]:
    capstore.seed_if_empty()
    out = []
    for b in _registry():
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
                             "authorised_line": d.get("authorised_line")})
        out.append({"binder": b, "versions": versions,
                    "current": capstore.current(bid)})
    return out


# list_proposals: every proposal record.
def list_proposals() -> list[dict]:
    return mc.list_proposals(PROPOSALS_DIR)


# get_proposal: one proposal record, or None.
def get_proposal(proposal_id: str) -> dict | None:
    return mc.get_proposal(PROPOSALS_DIR, proposal_id)


# create_proposal: validate and persist a draft authorised-line change.
def create_proposal(binder_id: str, authorised_line, author: str,
                    effective_from: str, summary: str = "") -> dict:
    if binder_id not in _binder_ids():
        raise ValueError(f"unknown binder {binder_id}")
    # Seed the v1 baseline first: an approval must supersede history, never
    # become v1 by winning a race against the seed.
    capstore.seed_if_empty()
    try:
        line = float(authorised_line)
    except (TypeError, ValueError):
        raise ValueError("authorised line must be a number")
    if line < 0:
        raise ValueError("authorised line cannot be negative")
    payload = {"authorised_line": line}
    return mc.create_proposal(PROPOSALS_DIR, binder_id, payload, author,
                              effective_from, summary, payload_key="capacity")


# _build_version: the immutable version document written on approval.
def _build_version(proposal: dict, version: int, supersedes: int | None,
                   approver: str) -> dict:
    return {"binder_id": proposal["binder_id"],
            "authorised_line": float(proposal["capacity"]["authorised_line"]),
            "version": version,
            "effective_from": proposal["effective_from"],
            "effective_to": None,
            "supersedes": supersedes,
            "author": proposal["author"],
            "approver": approver}


# approve_proposal: four-eyes approval writes the next version file.
def approve_proposal(proposal_id: str, approver: str) -> dict:
    # A proposal can outlive the seed (fresh deploy, wiped versions dir): seed
    # before numbering so the approval supersedes v1 rather than replacing it.
    capstore.seed_if_empty()
    return mc.approve(PROPOSALS_DIR, VERSIONS_DIR, proposal_id, approver,
                      _build_version, payload_key="capacity")


# rollback_proposal: propose restoring a previous version's line.
def rollback_proposal(binder_id: str, target_version: int, author: str,
                      effective_from: str, summary: str = "") -> dict:
    capstore.seed_if_empty()
    old = mc.load_version(VERSIONS_DIR, binder_id, target_version)
    return create_proposal(binder_id, old["authorised_line"], author,
                           effective_from,
                           summary or f"Rollback to v{target_version}")


# diff_versions: field-level comparison of two authorised-line versions.
def diff_versions(binder_id: str, v1: int, v2: int) -> dict:
    capstore.seed_if_empty()
    d1 = mc.load_version(VERSIONS_DIR, binder_id, v1)
    d2 = mc.load_version(VERSIONS_DIR, binder_id, v2)
    return {"v1": v1, "v2": v2,
            "before": d1.get("authorised_line"),
            "after": d2.get("authorised_line"),
            "effective_from": {"v1": d1.get("effective_from"),
                               "v2": d2.get("effective_from")},
            "changed": mc.changed_fields(d1, d2)}


# _tiv: the submission TIV a sample case describes, if it has one.
def _tiv(raw: dict) -> float | None:
    for doc in raw.get("documents", []):
        hint = (doc or {}).get("structured_hint") or {}
        if hint.get("total_insured_value") is not None:
            try:
                return float(hint["total_insured_value"])
            except (TypeError, ValueError):
                return None
    return None


# dry_run_proposal: how many sample cases change eligibility if the line moves.
def dry_run_proposal(binder_id: str, proposed_line, case_ids: list[str]) -> dict:
    from nodes import capacity as cap

    capstore.seed_if_empty()
    current_line = capstore.line_for(binder_id)
    new_line = float(proposed_line)
    written = 0.0
    reserved = 0.0
    try:
        ledger = ledger_mod.load()
        bb = ledger.get("binders", {}).get(binder_id, {})
        written = float(bb.get("written_to_date") or 0.0)
        reserved = ledger_mod._active_reserved(bb)
    except Exception:
        pass

    ids = case_ids or [f[:-5] for f in sorted(os.listdir(CASE_DIR))
                       if f.endswith(".json")]
    flips = []
    skipped = 0
    for cid in ids:
        path = os.path.join(CASE_DIR, cid + ".json")
        if not os.path.exists(path):
            skipped += 1
            continue
        tiv = _tiv(json.load(open(path, encoding="utf-8")))
        if tiv is None:
            skipped += 1
            continue
        before = cap.screen({"extracted": {"total_insured_value": tiv}},
                            current_line, written, reserved)["binder_outcome"]
        after = cap.screen({"extracted": {"total_insured_value": tiv}},
                           new_line, written, reserved)["binder_outcome"]
        if before != after:
            flips.append({"case": cid, "tiv": tiv,
                          "before": before, "after": after})

    def _utilisation(line: float) -> float:
        return round((written + reserved) / line * 100, 1) if line else 0.0

    return {"binder_id": binder_id, "total": len(ids), "skipped": skipped,
            "current_line": current_line, "proposed_line": new_line,
            "written": written, "reserved": reserved,
            "available": {"before": current_line - written - reserved,
                          "after": new_line - written - reserved},
            "utilisation": {"before": _utilisation(current_line),
                            "after": _utilisation(new_line)},
            "changed": len(flips), "details": flips}
