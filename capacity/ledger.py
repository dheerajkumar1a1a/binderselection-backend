"""Capacity ledger: reservations, bind write-back, idempotency (BFR-CAP-008/009, NFR-017, CON-4).

File-backed for the slice (JSON with temp-rename writes). Production needs a
transactional store with row locks - see note in reserve().
Ledger shape per binder:
  {written_to_date, reservations: {res_id: {submission_ref, amount, expires_at}}}
Available = authorised_line - written - sum(active reservations), where the
authorised line comes from the versioned capacity store (ADR-0002) and is never
duplicated into the ledger.
Idempotency: key = submission_ref + binder. Repeat calls return the original
reservation; binds record processed keys so retries never double-write.
"""
# json: serialise ledger.
import json
# os: env var for ledger path.
import os
# sys: import the repo's capacity store without relying on sys.path.
import sys
# uuid: reservation ids.
import uuid
# datetime: expiry timestamps.
from datetime import datetime, timedelta, timezone
# Path: filesystem paths.
from pathlib import Path

# BASE: capacity dir.
BASE = Path(__file__).resolve().parent
# LEDGER_PATH: env-overridable ledger file.
LEDGER_PATH = Path(os.environ.get("BINDER_LEDGER", str(BASE / "ledger.json")))
# Reservation TTL in hours.
RESERVATION_TTL_HOURS = int(os.environ.get("BINDER_RES_TTL_HOURS", "24"))


# _line_for: the authorised line in force, from the versioned store.
def _line_for(binder_id: str) -> float:
    sys.path.insert(0, str(BASE.parent))
    from capacity import store as capstore
    return capstore.line_for(binder_id)



# _now: current UTC time.
def _now() -> datetime:
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


# _empty_binder: default binder ledger entry. The authorised line is not stored
# here — it is read from the versioned capacity store (ADR-0002).
def _empty_binder() -> dict:
    return {"written_to_date": 0.0,
            "reservations": {}, "processed_binds": []}


# load: read ledger from disk (or empty default). A legacy `authorised_line`
# left in an old file is dropped on read: the line lives only in the versioned
# store (ADR-0002), and a stale copy must never be reachable by a caller.
def load() -> dict:
    if not LEDGER_PATH.exists():
        return {"binders": {"binder_A": _empty_binder()}}
    ledger = json.loads(LEDGER_PATH.read_text())
    for b in ledger.get("binders", {}).values():
        b.pop("authorised_line", None)
    return ledger


# _save: atomic write via temp rename. Drops the legacy authorised_line copy so
# an old ledger file migrates itself on first write.
def _save(ledger: dict) -> None:
    for b in ledger.get("binders", {}).values():
        b.pop("authorised_line", None)
    tmp = LEDGER_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2))
    tmp.replace(LEDGER_PATH)


# _active_reserved: sum of non-expired reservations.
def _active_reserved(binder: dict) -> float:
    now = _now()
    total = 0.0
    for r in binder.get("reservations", {}).values():
        if datetime.fromisoformat(r["expires_at"]) > now:
            total += r["amount"]
    return total


# available: free capacity for a binder.
def available(binder_id: str, ledger: dict | None = None) -> float:
    ledger = ledger if ledger is not None else load()
    b = ledger["binders"].get(binder_id)
    if b is None:
        raise KeyError(f"unknown binder {binder_id}")
    return _line_for(binder_id) - b["written_to_date"] - _active_reserved(b)


# reserve: reserve amount, idempotent on (submission_ref, binder).
def reserve(binder_id: str, submission_ref: str, amount: float) -> dict:
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    # Idempotency: return existing reservation if present.
    for res_id, r in b.get("reservations", {}).items():
        if r.get("submission_ref") == submission_ref:
            return {"reservation_id": res_id, "deduped": True,
                    "available": available(binder_id, ledger)}
    # Insufficient capacity → error.
    if available(binder_id, ledger) < amount:
        raise ValueError(f"insufficient capacity: available={available(binder_id, ledger)} need={amount}")
    # Create new reservation.
    res_id = f"res-{uuid.uuid4().hex[:8]}"
    b["reservations"][res_id] = {
        "submission_ref": submission_ref, "amount": amount,
        "created_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(hours=RESERVATION_TTL_HOURS)).isoformat()}
    _save(ledger)
    return {"reservation_id": res_id, "deduped": False,
            "available": available(binder_id, ledger)}


# release: remove reservations for a submission.
def release(submission_ref: str, binder_id: str) -> dict:
    ledger = load()
    b = ledger["binders"].get(binder_id, {})
    removed = [k for k, r in b.get("reservations", {}).items()
               if r.get("submission_ref") == submission_ref]
    for k in removed:
        del b["reservations"][k]
    _save(ledger)
    return {"released": len(removed)}


# bind: convert reservation to written (idempotent).
def bind(binder_id: str, submission_ref: str, amount: float) -> dict:
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    key = f"{binder_id}:{submission_ref}"
    # Already processed → deduped.
    if key in b.get("processed_binds", []):
        return {"deduped": True, "written_to_date": b["written_to_date"]}
    # Release reservation then write.
    release(submission_ref, binder_id)
    ledger = load()
    b = ledger["binders"].setdefault(binder_id, _empty_binder())
    b["written_to_date"] += amount
    b.setdefault("processed_binds", []).append(key)
    _save(ledger)
    return {"deduped": False, "written_to_date": b["written_to_date"]}


# cancel: reverse a bind.
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
