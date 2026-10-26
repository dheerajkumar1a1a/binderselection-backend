"""Capacity desk (phase 6): ledger-aware screening + alerts + MI.

Eligibility comes from the versioned authorised line (capacity/store.py,
ADR-0002); the live ledger contributes written business and reservations.
The desk overlays ledger figures onto the engine's payload so the workboard and
case page reflect real reservations. Alerts (80%/90%) fire at the moment a
reservation crosses the threshold, emailed to the placing underwriter + admins.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from capacity import ledger as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _line_for(binder_id: str, fallback: float = 15_000_000.0) -> float:
    """Authorised line in force, from the versioned capacity store (ADR-0002)."""
    try:
        sys.path.insert(0, ROOT)
        from capacity import store as capstore
        return capstore.line_for(binder_id)
    except (KeyError, FileNotFoundError, ValueError):
        return fallback


def augment_payload(state: dict) -> None:
    """Overlay live ledger figures onto each binder's capacity_snapshot."""
    for b in state.get("binder_results") or []:
        bid = b.get("binder_id")
        if not bid:
            continue
        try:
            line = _line_for(bid)
            ledger = L.load()
            if bid not in ledger.get("binders", {}):
                ledger["binders"][bid] = L._empty_binder()
                L._save(ledger)
            avail = L.available(bid)
            bb = ledger["binders"][bid]
            snap = b.setdefault("capacity_snapshot", {})
            snap["authorised_line"] = line
            snap["written_to_date"] = bb.get("written_to_date")
            snap["reserved"] = round(line - bb.get("written_to_date", 0) - avail, 2)
            snap["available_capacity"] = avail
        except Exception:
            pass


def desk() -> list[dict]:
    """Per-binder capacity desk summary, including binders with no ledger row yet."""
    ledger = L.load()
    known = set(ledger.get("binders", {}))
    try:
        sys.path.insert(0, ROOT)
        from capacity import store as capstore
        known |= {b["binder_id"] for b in capstore._binders() if b.get("binder_id")}
    except Exception:
        pass
    out = []
    for bid in sorted(known):
        bb = ledger.get("binders", {}).get(bid) or L._empty_binder()
        line = _line_for(bid)
        written = bb.get("written_to_date", 0.0)
        reserved = L._active_reserved(bb)
        avail = line - written - reserved
        pct = (written + reserved) / line if line else 0.0
        try:
            sys.path.insert(0, ROOT)
            from capacity import store as capstore
            version = capstore.current(bid)
        except Exception:
            version = None
        out.append({"binder_id": bid, "authorised_line": line,
                    "written_to_date": written, "reserved": reserved,
                    "available": avail, "utilisation": round(pct * 100, 1),
                    "alert": "breached" if pct >= 0.9 else ("warn" if pct >= 0.8 else "ok"),
                    "reservations": bb.get("reservations", {}),
                    "version": version})
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