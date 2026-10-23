"""Capacity desk (phase 6): ledger-aware screening + alerts + MI.

The demo engine still screens against static capacity.json (engine logic,
unchanged). Production augments the resulting payload with the live ledger's
reserved/written/available figures so the workboard and case page reflect real
reservations. Alerts (80%/90%) fire at the moment a reservation crosses the
threshold (settled grill answer), emailed to the placing underwriter + admins.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from capacity import ledger as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _binder_lines() -> dict[str, float]:
    """Authorised lines from the static capacity.json (the demo's source)."""
    try:
        data = json.load(open(os.path.join(ROOT, "rules", "capacity.json"),
                              encoding="utf-8"))
        return {b["binder_id"]: float(b.get("authorised_line", 15_000_000))
                for b in data.get("binders", [])}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def augment_payload(state: dict) -> None:
    """Overlay live ledger figures onto each binder's capacity_snapshot."""
    for b in state.get("binder_results") or []:
        bid = b.get("binder_id")
        if not bid:
            continue
        try:
            ledger = L.load()
            if bid not in ledger.get("binders", {}):
                line = _binder_lines().get(bid, 15_000_000.0)
                ledger["binders"][bid] = L._empty_binder(line)
                L._save(ledger)
            avail = L.available(bid)
            bb = ledger["binders"][bid]
            snap = b.setdefault("capacity_snapshot", {})
            snap["authorised_line"] = bb.get("authorised_line")
            snap["written_to_date"] = bb.get("written_to_date")
            snap["reserved"] = round(bb.get("authorised_line", 0) -
                                    bb.get("written_to_date", 0) - avail, 2)
            snap["available_capacity"] = avail
        except Exception:
            pass


def desk() -> list[dict]:
    """Per-binder capacity desk summary."""
    ledger = L.load()
    lines = _binder_lines()
    out = []
    for bid, bb in ledger.get("binders", {}).items():
        line = bb.get("authorised_line", lines.get(bid, 0.0))
        written = bb.get("written_to_date", 0.0)
        reserved = L._active_reserved(bb)
        avail = line - written - reserved
        pct = (written + reserved) / line if line else 0.0
        out.append({"binder_id": bid, "authorised_line": line,
                    "written_to_date": written, "reserved": reserved,
                    "available": avail, "utilisation": round(pct * 100, 1),
                    "alert": "breached" if pct >= 0.9 else ("warn" if pct >= 0.8 else "ok"),
                    "reservations": bb.get("reservations", {})})
    return sorted(out, key=lambda x: x["binder_id"])


def check_alerts(binder_id: str, placed_by: str | None = None) -> list[str]:
    """Email underwriter+admins if a binder crossed 80%/90% after a new
    reservation. Returns the alert levels fired (for tests)."""
    from prod import mail as mail_mod
    for bb in desk():
        if bb["binder_id"] != binder_id:
            continue
        level = bb["alert"]
        if level == "ok":
            return []
        recipients = mail_mod.staff_recipients()
        if placed_by and placed_by not in recipients:
            recipients = recipients + [placed_by]
        mail_mod.send(", ".join(recipients),
                      f"{binder_id} capacity {bb['utilisation']}% utilised",
                      f"{binder_id} is now at {bb['utilisation']}% of its "
                      f"authorised line (written {bb['written_to_date']:,.0f}, "
                      f"reserved {bb['reserved']:,.0f}, available {bb['available']:,.0f}).\n"
                      f"Alert level: {level} (80%/90% thresholds).")
        return [level]
    return []