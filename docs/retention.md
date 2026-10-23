# Retention policy (phase 6 loose end)

Decided: **7 years** for all decision-relevant records.

## What is retained

- `Case`, `Evaluation`, `Decision` rows (append-only, never deleted).
- Audit records under `audit/decisions.jsonl` and `audit/` evidence packs.
- Documents under `data/cases/<case_id>/` (manifest + raw bytes).
- Capacity ledger (`data/` or `BINDER_LEDGER` path) — reservations, binds, processed-bind keys.
- Outbox mail under `data/outbox/` (notification proof).

## Mechanism (v1, manual)

Retention is **documented policy, not yet automated** (settled grill answer: document now,
mechanise later). Until an archive job exists:

1. Do not delete or truncate `data/`, the SQLite/Postgres database, or `audit/`.
2. On a yearly cadence, snapshot the whole `data/` tree plus a database dump into an
   archive location outside the live working directory (e.g. `archive/YYYY/`), then
   verify the snapshot restores before any cleanup.
3. Nothing is auto-deleted; any future archive/expiry job must be explicit, reviewed,
   and reversible, and must never touch records younger than 7 years.

## Out of scope for v1

- Automated archival, compression, or deletion.
- Per-tenant retention windows (single-tenant only).
- Legal-hold overrides (add when a real matter requires it).
