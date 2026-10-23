# ADR 0001 — One Case, successor evaluations on it, one active Request round

Date: 2026-10-23 · Status: accepted · Decided in the phase-3 grill

## Context

When a broker answers an information request (or new documents arrive), the
engine must re-evaluate. Two shapes were possible:

- **Fork**: the refer-back opens a *new Case* linked to the old one.
- **Successor**: the *same Case* gains an append-only successor evaluation.

The case page previously said "a fresh submission opens a successor case",
while CONTEXT.md (glossary) defined a **Successor evaluation** on the same
Case — a contradiction that had to be settled before building.

A related shape question: how many Request rounds may be open at once, and
what unit the broker answers / the answer-SLA clock runs on.

## Decision

1. **A Case never forks.** Every re-evaluation appends a successor
   `Evaluation` on the same `Case`. The lineage section shows the chain;
   decisions always bind to the evaluation they were recorded on; the human
   decides on the freshest one.
2. **One active Request round per Case.** A round is a named batch of
   information requests issued together, answered together — one SLA clock
   (10 business days), one submission that locks it. After a locked round's
   successor evaluation, if gaps remain the underwriter may issue a new round.
3. **`bound` is terminal for this release.** A decided+reserved Case stays
   bound; nothing rewrites decisions. Corrections still have a door: a
   successor evaluation may be run and a *new* decision recorded on it —
   history is never overwritten, the pointer fields simply move forward.
   `awaiting-broker` is the open-round state between evaluation and the
   broker's answer.

## Consequences

- No case-id graph, no cross-case provenance stitching; history reads top to
  bottom on one page.
- The round is the natural provenance unit for broker-supplied data (typed
  portal answers and/or attached documents enter the next evaluation through
  one "answer sheet" document + uploads), so every broker fact carries its
  round number.
- Explicitly rejected: free-standing loose items per case (indefinite number
  of answerable things, ambiguous SLA), and forked cases (two "current"
  places to decide).
