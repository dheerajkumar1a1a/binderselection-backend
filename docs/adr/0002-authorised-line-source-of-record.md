# 0002 — Versioned capacity files are the source of record for the Authorised line

Date: 2026-10-27
Status: accepted

## Context

The authorised line — the ceiling a binder's capacity is measured against — lived in
two places that mutated independently:

- `rules/capacity.json`, a static seed with no writer, read by the engine via
  `nodes/multibind.py:33-37` → `nodes/capacity.py:5-22` to decide eligibility and to
  weight ranking.
- `capacity/ledger.json`, written by `capacity/ledger.py` on reserve/release and read
  by the desk UI via `prod/capacity_desk.py:60-76`.

Nothing reconciled them. `capacity_desk.augment_payload` (`:36-57`) even overwrote the
engine's own `capacity_snapshot` after a run, so the number a user saw on the desk and
the number that had actually screened the submission could differ with no signal.

Adding maker-checker approval on top of this would have produced a third copy: approve a
proposal, write a version file, and neither the engine nor the desk would read it. The
feature would have appeared to work while changing nothing.

## Decision

Versioned capacity files are the single source of record for the authorised line.

- Versions live at `capacity/versions/binder_<id>_v<N>.json`, with an independent
  per-binder counter (capacity v2 is unrelated to rules v5).
- v1 is seeded once, idempotently, from `rules/capacity.json`, carrying the binder's own
  `effective_from` from `rules/binders.json` so the seed reads as history rather than as
  a change effective today.
- `capacity/ledger.json` drops its `authorised_line` field and reads the effective
  version, so desk and engine cannot drift.
- `written_to_date` stays operational data in the ledger. It is never authored and never
  versioned: a version file describes only what a human decided.
- `rules/capacity.json` is retained read-only as a fallback when no version file exists
  for a binder, with a logged warning, and removed in a later change.

## Consequences

- Approval changes eligibility immediately; there is no separate publish step.
- The desk's "Available / Utilisation" and the engine's exclusion decision are derived
  from one number.
- Seed-time conflict is resolved in favour of `rules/capacity.json`, the number
  underwriting has actually been screened against.
- A half-migrated directory degrades to the previous behaviour rather than excluding
  every binder (fail-soft), while `screen_safe` continues to fail closed per binder.
- `rules/capacity.json` becomes dead weight that must be deleted deliberately, not
  forgotten.

## Alternatives rejected

- **Keep `rules/capacity.json` canonical and rewrite it in place on approval.** Gains
  history only in proposal records; the versioning machinery would be decorative.
- **Desk-only bookkeeping.** Would leave the number that decides eligibility untouched —
  the exact "approved but nothing changed" failure this ADR exists to prevent.
- **Leave `rules/capacity.json` as a permanent override.** Would silently re-create the
  two-sources bug.
