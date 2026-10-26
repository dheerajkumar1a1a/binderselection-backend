"""Versioned authorised lines: the source of record for binder capacity.

See docs/adr/0002-authorised-line-source-of-record.md.

Layout:

    capacity/versions/binder_<id>_v<N>.json   approved, immutable lines
    capacity/proposals/P-<8 hex>.json         maker-checker proposals

A version document carries only what a human authored: the authorised line,
plus the usual effective-dating and provenance keys. Written business and
reservations are operational ledger data and never appear here.

``rules/capacity.json`` is retained read-only as a fallback for binders that
have no version file yet (fail-soft during migration), and is expected to be
deleted in a later change.
"""
from __future__ import annotations

# json: version documents, seed file, binder registry.
import json
# os: paths.
import os
# sys: make the repo importable without relying on the caller's sys.path.
import sys
# Path: filesystem paths.
from pathlib import Path
# date: effective-date resolution.
from datetime import date

_sys_path_added = False


def _ensure_importable() -> None:
    global _sys_path_added
    if not _sys_path_added:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        _sys_path_added = True


# BASE: capacity directory. ROOT: repo root.
BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
VERSIONS_DIR = BASE / "versions"
PROPOSALS_DIR = BASE / "proposals"
SEED_PATH = ROOT / "rules" / "capacity.json"
BINDERS_PATH = ROOT / "rules" / "binders.json"


# _binders: binder registry entries.
def _binders() -> list[dict]:
    try:
        return json.loads(BINDERS_PATH.read_text())["binders"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return []


# legacy_line: the pre-versioning number, or None when the seed is absent.
def legacy_line(binder_id: str) -> float | None:
    try:
        data = json.loads(SEED_PATH.read_text())
        entry = data.get("binders", {}).get(binder_id)
        if entry is None:
            return None
        return float(entry.get("authorised_line"))
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


# version_docs: stored version documents for a binder, oldest first.
def version_docs(binder_id: str) -> list[dict]:
    _ensure_importable()
    from prod import maker_checker as mc
    return mc.list_versions(str(VERSIONS_DIR), binder_id)


# seed_if_empty: write v1 for every binder that has none, from the legacy seed.
# Idempotent: safe to call on every request.
def seed_if_empty() -> int:
    written = 0
    for b in _binders():
        binder_id = b.get("binder_id")
        if not binder_id:
            continue
        if version_docs(binder_id):
            continue
        line = legacy_line(binder_id)
        if line is None:
            # No seeded number to inherit; leave the binder unversioned so the
            # engine's fallback path reports it rather than inventing a line.
            continue
        doc = {"binder_id": binder_id,
               "authorised_line": line,
               "version": 1,
               "effective_from": b.get("effective_from") or "2026-01-01",
               "effective_to": None,
               "supersedes": None,
               "author": "system",
               "approver": "system"}
        path = VERSIONS_DIR / f"{binder_id}_v1.json"
        VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2))
        written += 1
    return written


# load_effective: the version in force for a binder on a date.
def load_effective(binder_id: str, as_at: str | None = None) -> dict:
    as_at = as_at or date.today().isoformat()
    best = None
    for entry in version_docs(binder_id):
        data = entry["data"]
        starts = data.get("effective_from", "")
        ends = data.get("effective_to")
        if starts <= as_at and (ends is None or ends >= as_at):
            if best is None or data.get("version", 0) > best.get("version", 0):
                best = data
    if best is None:
        raise FileNotFoundError(
            f"no effective capacity version for {binder_id} at {as_at}")
    return best


# line_for: the authorised line in force, falling back to the legacy seed.
def line_for(binder_id: str, as_at: str | None = None) -> float:
    seed_if_empty()
    try:
        return float(load_effective(binder_id, as_at)["authorised_line"])
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        legacy = legacy_line(binder_id)
        if legacy is None:
            raise KeyError(f"no capacity record for {binder_id} (BFR-CAP-012)")
        return legacy


# current: version metadata for display (version number + effective date).
def current(binder_id: str, as_at: str | None = None) -> dict | None:
    try:
        doc = load_effective(binder_id, as_at)
    except FileNotFoundError:
        return None
    return {"version": doc.get("version"),
            "effective_from": doc.get("effective_from"),
            "authorised_line": doc.get("authorised_line"),
            "author": doc.get("author"),
            "approver": doc.get("approver")}
