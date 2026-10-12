# Rules data package

This folder holds the deterministic policy and reference data used by the Binder Selection Agent. It is the source of truth for binder availability, rule eligibility, scoring, and override governance, and it is intentionally separated from the Python execution logic so that business rules can be reviewed, versioned, and changed without modifying application code.

The folder is designed around a simple principle:

- the workflow code evaluates submissions using JSON-defined rules
- rules are versioned and time-scoped
- binders are registered with lifecycle metadata
- scoring is configurable without changing the ranking engine
- underwriter overrides are constrained to approved reason codes

This makes the decision logic auditable, explainable, and easier to test.

---

## Purpose

The `rules/` package is responsible for the following:

- defining which binders are active and when they are in force
- storing approved binder rulesets in versioned files
- keeping the rules source separate from business logic
- evaluating threshold-based eligibility checks
- providing deterministic scoring inputs for ranking
- controlling override logic for human review decisions
- acting as a reference layer for admin and governance features

In other words, this folder contains the policy layer for the repo, while the Python modules under `nodes/` and `capacity/` contain execution logic that consumes that policy.

---

## Folder layout

```text
rules/
├── README.md                         # This file
├── binders.json                      # Binder registry and active status
├── binder_A_v1.json                  # Approved versioned ruleset for Binder A
├── binder_B_v1.json                  # Approved versioned ruleset for Binder B
├── capacity.json                     # Stand-in capacity source data
├── scoring.json                      # Scoring weights and tie-break configuration
├── override_reason_codes.json        # Valid underwriter override reasons
├── store.py                          # Rule lifecycle and validation helpers
```

---

## Core concepts

### 1. Binder registry

`binders.json` defines the legal registry of binders and their effective lifecycle:

```json
{
  "binders": [
    {
      "binder_id": "binder_A",
      "binder_name": "Binder A",
      "status": "active",
      "effective_from": "2026-01-01",
      "effective_to": null,
      "strategic_classification": "preferred"
    }
  ]
}
```

Important fields:

- `binder_id`: system identifier used by the engine
- `binder_name`: human-friendly label
- `status`: active, suspended, retired, etc.
- `effective_from`: date the binder becomes valid
- `effective_to`: optional end date for expiration
- `strategic_classification`: classification used by ranking or governance logic

This registry is used by modules that must determine which binders are currently eligible to be evaluated.

### 2. Versioned rulesets

Each approved binder ruleset is stored as a file named:

```text
binder_<id>_v<version>.json
```

Examples:

- `binder_A_v1.json`
- `binder_B_v1.json`

These files are versioned so a binder's rule logic can be changed over time without rewriting code. Every ruleset contains metadata like:

- `binder_id`
- `version`
- `effective_from`
- `effective_to`
- `author`
- `approver`
- `notes`
- `rules`

Each rule entry typically includes:

- `rule_id`: unique identifier for the rule
- `category`: business category or topic
- `scope`: submission or location-level evaluation
- `field_reference`: the data field being tested
- `operator`: comparison operator (for example `lte`, `gte`, `is_true`, `not_in`)
- `threshold_value`: the threshold or set value to compare against
- `threshold_unit`: the data type or unit for the threshold
- `severity`: rule severity such as `refer`
- `logic_group` / `logic`: optional grouping metadata for rule combinations
- `business_description`: plain-language explanation of the rule

This provides a clean separation between programmatic evaluation and natural-language business intent.

### 3. Effective rules selection

The repo is designed to apply the right ruleset for a given binder and date. The `store.py` helper identifies the highest-version ruleset that is effective for the requested date. This allows a binder to have multiple approved rule revisions over time without hard-coding date logic into the decision engine.

### 4. Scoring

`scoring.json` defines the ranking model used to compare eligible binders:

```json
{
  "version": 1,
  "max_score": 10,
  "weights": {
    "available_capacity": 5,
    "strategic_classification": 2,
    "appetite_fit": 3
  },
  "strategic_points": {
    "preferred": 2,
    "standard": 0
  },
  "tie_break": ["available_capacity", "binder_id"]
}
```

This file decouples scoring policy from ranking code. If the weighting or tie-break logic changes, the model can be updated here rather than revising the Python implementation.

### 5. Capacity reference data

`capacity.json` is a stand-in source for the binder capacity model used by the vertical slice. It is intentionally simple and file-based, representing a placeholder for a future real capacity source: a system of record that tracks:

- authorised line
- written to date
- reserved capacity

The current structure is:

```json
{
  "note": "Stand-in capacity source of record",
  "binders": {
    "binder_A": {"authorised_line": 15000000.0, "written_to_date": 5000000.0, "reserved": 0.0},
    "binder_B": {"authorised_line": 20000000.0, "written_to_date": 4000000.0, "reserved": 0.0}
  }
}
```

This acts as a deterministic input for rule evaluation and binder eligibility.

### 6. Override reasons

`override_reason_codes.json` provides the approved set of reasons an underwriter may use when overriding a recommendation:

- `PRIOR_RELATIONSHIP`
- `CAPACITY_PREFERENCE`
- `TERMS_NEGOTIATED`
- `BROKER_REQUEST`
- `OTHER`

These codes are used during human review to ensure overrides are not arbitrary and are captured consistently in the audit trail.

---

## File-by-file reference

### `binders.json`

Purpose:

- defines the binder registry and lifecycle metadata
- marks binder status and validity dates
- links binder IDs to human-readable names and strategic class

Use:

- load active binders for evaluation
- determine whether a binder is currently in force
- support lifecycle management without code changes

### `binder_A_v1.json`

Purpose:

- first approved ruleset for binder A
- contains the initial set of binder appetite and exposure checks

Key rules in the current version include:

- `A-002-TIV`: total insured value maximum threshold
- `A-005-SPRINKLER`: sprinkler requirement at location level
- `A-009-COMMODITY`: commodity exclusion list

This file demonstrates how a binder's business appetite is represented as structured, serialisable rules instead of hard-coded Python logic.

### `binder_B_v1.json`

Purpose:

- first approved ruleset for binder B
- includes more complex geographic, valuation, and construction-based rules

Examples of the rules include:

- territory exclusions
- wildfire and flood zone checks
- prior cancellation / non-renewal checks
- frame and alarm logic combinations
- valuation basis constraints
- profit share / no-claims-bonus exclusions
- commodity exclusions

This file is more complex than binder A and illustrates rule grouping and compound logic.

### `capacity.json`

Purpose:

- stand-in source for binder capacity record
- gives each binder a line, written amount, and reserved amount
- supports deterministic capacity checks in the vertical slice

This file is intentionally simple and acts as a temporary placeholder until the real source-of-record system is connected.

### `scoring.json`

Purpose:

- stores scoring configuration for ranking eligible binders
- defines weights, strategic classification points, and tie-break logic

This keeps the ranking model data-driven and transparent.

### `override_reason_codes.json`

Purpose:

- restricts underwriter override reasons to an approved code list
- provides human-readable descriptions for each code

This supports governance and auditability in the human review step.

### `store.py`

Purpose:

- rule administration utilities for versioning, validation, and approval flow
- lifecycle management for rulesets and binder statuses

Core functions include:

- `validate_rule(rule)`
- `_binder_files(binder_id)`
- `load_effective(binder_id, as_at=None)`
- `is_active(binder_id, as_at=None, registry=None)`
- `propose(ruleset, author)`
- `approve(proposal, approver)`
- `dry_run(cases, current, proposed)`

This module is the governance and admin layer for rule data. It enforces basic quality checks and supports four-eyes approval workflows.

---

## Rule evaluation model

Rules in this folder are written to be evaluated by Python code in a deterministic way. A common structure is:

```json
{
  "rule_id": "A-002-TIV",
  "category": "Total Insured Value",
  "scope": "submission",
  "field_reference": "total_insured_value",
  "operator": "lte",
  "threshold_value": 10000000,
  "threshold_unit": "currency",
  "severity": "refer"
}
```

This is evaluated like:

```python
field_value <= 10000000
```

The actual engine may support operators such as:

- `lte`, `lt`
- `gte`, `gt`
- `eq`, `neq`
- `in`, `not_in`
- `is_true`, `is_false`
- `is_absent`, `is_present`
- `before`, `after`

The evaluation engine reads the JSON file and produces rule outcomes like:

- `Pass`
- `Decline`
- `Cannot-assess`

This allows the repo to remain explicit about the difference between a true business decline and a missing-data / evaluation-block condition.

---

## Governance and maintenance

This folder is not just static config; it is part of the compliance and oversight process.

The repository design expects the following operational patterns:

- rules are reviewed and approved before being used in production
- rules are versioned rather than overwritten in place
- changes are tracked with explicit author and approver information
- dry-run checks can compare current versus proposed outcomes before approval
- binder status can change without code changes by editing the registry

This is important for a decision-support workflow where changes to underwriting appetite have legal and operational impact.

---

## Relationship to the rest of the repo

The rules folder sits between the application code and the business policy:

- `nodes/` executes evaluation, ranking, and narrative steps
- `rules/` provides logic inputs, thresholds, and status metadata
- `capacity/` provides ledger-based capacity accounting
- `persistence.py` writes the final decision records for audit

The design separation is intentional:

- business logic is data-driven
- business policy can be reviewed as configuration
- the runtime remains deterministic and testable

---

## Typical contributor workflow

When modifying rules, the usual process is:

1. inspect the active binder registry in `binders.json`
2. confirm the effective ruleset for the binder and date in the appropriate `binder_*_v*.json` file
3. validate the JSON structure and field references using `store.py`
4. run dry-run comparisons before approving changes
5. update tests if rule outcomes or ranking behavior change

This ensures that policy changes are deliberate and do not silently break the workflow.

---

## Summary

The `rules/` folder is the policy backbone of the binder selection system. It holds the binder registry, versioned appetite rules, scoring configuration, capacity reference data, and validation tools that keep the decision logic explainable and governable.

If you need to understand how binder eligibility is determined, this is the first folder to read after `nodes/` and before changing any business logic.

This folder is deliberately designed so that a person can review and approve underwriting rules without needing to understand the full implementation of the decision engine.

---

## Quick references

- Binder registry: `binders.json`
- Binder A rules: `binder_A_v1.json`
- Binder B rules: `binder_B_v1.json`
- Scoring: `scoring.json`
- Capacity placeholder: `capacity.json`
- Override reasons: `override_reason_codes.json`
- Rule administration: `store.py`
