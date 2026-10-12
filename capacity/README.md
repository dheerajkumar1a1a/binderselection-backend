# Capacity module

This folder contains the binder-capacity ledger used by the Binder Selection Agent. Its job is to track how much of each binder's authority is still available, reserve capacity while a submission is under review, and record accepted binds without allowing duplicate writes or double-counting.

The implementation is intentionally simple and file-backed for the current vertical slice. It follows the design described in the project-level README: capacity is deterministic, explainable, and separate from LLM decisioning.

## Purpose

The capacity layer protects the system from three common failure modes:

- Double-booking the same submission against a binder
- Counting a reservation and a bind as if both were independent writes
- Allowing a submission to consume more capacity than the binder authorises

Each binder is modelled as a ledger record with:

- `authorised_line`: the maximum capacity available to the binder
- `written_to_date`: total already written and accepted
- `reservations`: active capacity reservations keyed by reservation id
- `processed_binds`: idempotency keys for already-processed binds

Available capacity is calculated as:

`authorised_line - written_to_date - sum(active reservations)`

## Files in this folder

### `__init__.py`
Empty package marker. This makes `capacity` importable as a Python package.

### `ledger.py`
The actual capacity state store and business logic. It provides:

- `load()` — load the ledger from disk
- `_save()` — persist the ledger atomically using temp-file rename
- `available()` — compute remaining available capacity
- `reserve()` — create an idempotent reservation for a submission
- `release()` — remove reservation(s) for a submission reference
- `bind()` — convert a submitted reservation into written capacity
- `cancel()` — reverse a previous bind write if needed

## Ledger shape

The ledger is stored as JSON and has this structure:

```json
{
  "binders": {
    "binder_A": {
      "authorised_line": 15000000.0,
      "written_to_date": 0.0,
      "reservations": {
        "res-12345678": {
          "submission_ref": "SUB-001",
          "amount": 5000000.0,
          "created_at": "2026-10-12T12:00:00+00:00",
          "expires_at": "2026-10-13T12:00:00+00:00"
        }
      },
      "processed_binds": ["binder_A:SUB-001"]
    }
  }
}
```

Notes:

- `processed_binds` is used to make a bind idempotent.
- Reservations expire after a TTL (`BINDER_RES_TTL_HOURS`, default `24` hours).
- A reservation is deduplicated by `(submission_ref, binder_id)`.
- The implementation writes to a temp file and then replaces the original file to reduce corruption risk.

## Core rules enforced

### 1. Capacity availability

A reservation is only possible if the binder still has enough free capacity:

```python
if available(binder_id, ledger) < amount:
    raise ValueError(f"insufficient capacity: available={...} need={...}")
```

This ensures the binder cannot over-commit.

### 2. Reservation idempotency

`reserve()` checks whether the same `(submission_ref, binder_id)` already exists. If it does, it returns the original reservation instead of creating a duplicate one.

### 3. Bind idempotency

`bind()` checks `processed_binds` before writing capacity again. If the exact bind key has already been processed, it returns a deduped result and does not increment the ledger a second time.

### 4. Reservation release

When a submission is no longer pending or a decision has been made, `release()` removes all reservations matching that submission reference from the binder.

### 5. Reverse write-back

`cancel()` can remove a previously processed bind if the system needs to unwind a decision, subject to the same processed-binds guard.

## Operational behaviour

### Default ledger path

The ledger path is resolved from the environment variable `BINDER_LEDGER` or defaults to a `ledger.json` file in this directory:

```python
LEDGER_PATH = Path(os.environ.get("BINDER_LEDGER", str(BASE / "ledger.json")))
```

This means the folder is effectively both the source of the logic and the default on-disk data store for a local slice.

### Reservation TTL

Reservations expire automatically based on `BINDER_RES_TTL_HOURS`, defaulting to 24 hours:

```python
RESERVATION_TTL_HOURS = int(os.environ.get("BINDER_RES_TTL_HOURS", "24"))
```

This prevents stale reservations from blocking legitimate future capacity indefinitely.

## Example usage

```python
from capacity.ledger import reserve, bind, available, release

res = reserve("binder_A", "SUB-001", 2_500_000.0)
print(res)

# {"reservation_id": "res-abc12345", "deduped": False, "available": 7500000.0}

written = bind("binder_A", "SUB-001", 2_500_000.0)
print(written)

# {"deduped": False, "written_to_date": 2500000.0}

print(available("binder_A"))

release("SUB-001", "binder_A")
```

## Integration with the wider application

This module sits between the decision logic and final settlement:

- The graph evaluates binders and determines whether a binder is eligible
- A selected binder may reserve capacity before final underwriter approval
- Once the decision is accepted, the bind is written to the ledger
- The capacity ledger is then part of the reproducible audit record

This aligns with the project requirement that the capacity decision remains deterministic and auditable rather than being inferred from the LLM.

## Production caveat

The file-backed design is appropriate for a vertical slice, but it is not sufficient for production-grade concurrency or multi-process writes.

The module docstring explicitly notes:

> Production needs a transactional store with row locks.

In a real deployment, this ledger should normally live in a transactional database with:

- row-level locking
- atomic transaction boundaries
- durable write-ahead logging
- explicit cleanup of expired reservations
- concurrency-safe ledger updates across multiple workers

## Suggested responsibilities for future evolution

1. Move the ledger to a transactional DB and keep the same API surface
2. Add explicit metrics for reservation expiry and bind cancellation
3. Enforce per-submission uniqueness at the database layer as well as in Python
4. Add tests for TTL expiry, insufficient-capacity failures, double-bind protection, and release behaviour
5. Emit audit events whenever capacity is reserved, released, written, or cancelled

## Summary

The `capacity` package is the accounting layer for binder availability. It keeps the system honest by ensuring capacity is not overcommitted, is idempotent across retries, and remains traceable through the binder decision lifecycle.

If you are working inside this folder, start with `ledger.py`; it contains the actual business logic and the failure/duplication protections that the rest of the binder-selection workflow depends on.

