"""Reference data (phase 5): third-party facts beside extracted values.

A reference fact is data, never a decision — the same provenance standard as
extraction, but the source is a feed rather than a document (CONTEXT.md).
Feeds live as JSON files under data/reference/<feed>.json:

    {
      "feed": "wildfire", "licence": "CC-BY 4.0", "fetched_at": "2026-10-23",
      "key_field": "territory",          # extracted field used to look up
      "records": { "CA": { "wildfire_risk_score": 7, "flood_tier": "X" }, ... }
    }

Multiple feeds merge; a feed wins on conflict (settled grill answer). Attach
runs at evaluation time so the reference facts are frozen into the payload
(append-only) and carry source/licence/timestamp with them.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, "data", "reference")


def _ensure_dir():
    os.makedirs(REF_DIR, exist_ok=True)


def list_feeds() -> list[dict]:
    _ensure_dir()
    out = []
    for fn in sorted(os.listdir(REF_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(REF_DIR, fn), encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append({"file": fn, "feed": d.get("feed", fn[:-5]),
                    "licence": d.get("licence", "—"),
                    "fetched_at": d.get("fetched_at", "—"),
                    "records": len(d.get("records", {})),
                    "key_field": d.get("key_field", "territory")})
    return out


def load_feeds() -> list[dict]:
    return [json.load(open(os.path.join(REF_DIR, f["file"]), encoding="utf-8"))
            for f in list_feeds()]


def attach(payload: dict) -> list[dict]:
    """Attach reference facts to an evaluation payload in place.

    Returns the list of facts attached (also stored at payload['reference_facts']).
    Looks up each extracted location by the feed's key_field; a missing key or
    missing feed yields nothing — never invents a value.
    """
    extracted = payload.get("extracted") or {}
    locations = extracted.get("locations") or []
    facts: list[dict] = []
    for feed in load_feeds():
        key_field = feed.get("key_field", "territory")
        records = feed.get("records") or {}
        for i, loc in enumerate(locations):
            if not isinstance(loc, dict):
                continue
            key = loc.get(key_field)
            rec = records.get(str(key)) if key is not None else None
            if not isinstance(rec, dict):
                continue
            for field, value in rec.items():
                facts.append({"location_index": i,
                              "territory": key,
                              "field": field, "value": value,
                              "feed": feed.get("feed"),
                              "source": f"feed:{feed.get('feed')}",
                              "licence": feed.get("licence", "—"),
                              "fetched_at": feed.get("fetched_at", "—"),
                              "attached_at": datetime.now().isoformat(timespec="seconds")})
    payload["reference_facts"] = facts
    return facts


def refresh_from_dir() -> int:
    """No-op-ish: feeds are read from disk at attach time. Returns feed count
    so the admin UI can confirm a refresh landed."""
    return len(list_feeds())