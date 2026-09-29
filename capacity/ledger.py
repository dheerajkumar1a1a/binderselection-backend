"""Capacity ledger: reservations, bind write-back, idempotency (BFR-CAP-008/009, NFR-017, CON-4).

File-backed for the slice (JSON with temp-rename writes). Production needs a
transactional store with row locks - see note in reserve().
Ledger shape per binder:
  {authorised_line, written_to_date, reservations: {res_id: {submission_ref, amount, expires_at}}}
Available = line - written - sum(active reservations).
Idempotency: key = submission_ref + binder. Repeat calls return the original
reservation; binds record processed keys so retries never double-write.
"""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
LEDGER_PATH = Path(os.environ.get("BINDER_LEDGER", str(BASE / "ledger.json")))
RESERVATION_TTL_HOURS = int(os.environ.get("BINDER_RES_TTL_HOURS", "24"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_binder(line: float = 15_000_000.0) -> dict:
    return {"authorised_line": line, "written_to_date": 0.0,
            "reservations": {}, "processed_binds": []}


def load() -> dict:
    if not LEDGER_PATH.exists():
        return {"binders": {"binder_A": _empty_binder()}}
    return json.loads(LEDGER_PATH.read_text())


def _save(ledger: dict) -> None:
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2))
    tmp.replace(LEDGER_PATH)


def _active_reserved(binder: dict) -> float:
    now = _now()
    total = 0.0
    for r in binder.get("reservations", {}).values():
        if datetime.fromisoformat(r["expires_at"]) > now:
            total += r["amount"]
    return total


def available(binder_id: str, ledger: dict | None = None) -> float:
    ledger = ledger if ledger is not None else load()
    b = ledger["binders"].get(binder_id)
    if b is None:
        raise KeyError(f"unknown binder {binder_id}")
    return b["authorised_line"] - b["written_to_date"] - _active_reserved(b)


def reserve(binder_id: str, submission_ref: str, amount: float) -> dict:
    """Reserve amount. Idempotent on (submission_ref, binder)."""
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    for res_id, r in b.get("reservations", {}).items():
        if r.get("submission_ref") == submission_ref:
            return {"reservation_id": res_id, "deduped": True,
                    "available": available(binder_id, ledger)}
    if available(binder_id, ledger) < amount:
        raise ValueError(f"insufficient capacity: available={available(binder_id, ledger)} need={amount}")
    res_id = f"res-{uuid.uuid4().hex[:8]}"
    b["reservations"][res_id] = {
        "submission_ref": submission_ref, "amount": amount,
        "created_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(hours=RESERVATION_TTL_HOURS)).isoformat()}
    _save(ledger)
    return {"reservation_id": res_id, "deduped": False,
            "available": available(binder_id, ledger)}


def release(submission_ref: str, binder_id: str) -> dict:
    ledger = load()
    b = ledger["binders"].get(binder_id, {})
    removed = [k for k, r in b.get("reservations", {}).items()
               if r.get("submission_ref") == submission_ref]
    for k in removed:
        del b["reservations"][k]
    _save(ledger)
    return {"released": len(removed)}


def bind(binder_id: str, submission_ref: str, amount: float) -> dict:
    """Convert reservation to written. Idempotent on processed_binds."""
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    key = f"{binder_id}:{submission_ref}"
    if key in b.get("processed_binds", []):
        return {"deduped": True, "written_to_date": b["written_to_date"]}
    release(submission_ref, binder_id)
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    b["written_to_date"] += amount
    b.setdefault("processed_binds", []).append(key)
    _save(ledger)
    return {"deduped": False, "written_to_date": b["written_to_date"]}


def cancel(binder_id: str, submission_ref: str, amount: float) -> dict:
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    key = f"{binder_id}:{submission_ref}"
    if key in b.get("processed_binds", []):
        b["written_to_date"] = max(0.0, b["written_to_date"] - amount)
        b["processed_binds"].remove(key)
        _save(ledger)
        return {"cancelled": True, "written_to_date": b["written_to_date"]}
    return {"cancelled": False, "written_to_date": b["written_to_date"]}
