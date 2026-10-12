# Reports module

This folder contains the management-information (MI) reporting utilities for the Binder Selection Agent. Its purpose is to turn persisted decision records into clear operational metrics that can be consumed by dashboards, audits, or human review workflows.

The reporting layer is intentionally lightweight and deterministic: it reads audit JSONL records, performs pure calculations over them, and exposes easy-to-test functions without depending on the rest of the runtime graph.

## Why this folder exists

The wider application records each execution in `audit/decisions.jsonl` as an immutable decision record. Those records capture:

- the extracted submission fields
- per-binder rule outcomes
- the recommendation and reviewer decision
- audit metadata, timestamps, and evidence
- stage timings when available

The `reports` package converts that raw event stream into business-facing metrics such as:

- total volume and outcome mix
- decline reasons by rule
- override rates and reasons
- missing-data and low-confidence data quality indicators
- referral reasons by field
- average stage timings for pipeline steps

This is the module that powers the MI/dashboard view described in the project README and the leadership UI.

## Folder contents

### `__init__.py`

Empty package marker. This allows `reports` to be imported as a Python package.

### `mi.py`

Core reporting implementation.

Key responsibilities:

- load decision records from a JSONL path
- summarise submission volume and outcome mix
- identify why binders declined
- calculate override behaviour and rates
- summarise missing fields and low-confidence values
- group refer-back reasons by missing field
- compute average timing per stage when stage timings exist

## Core functions

### `load(path: str | Path | None = None) -> list[dict]`

Loads decision records from the default path:

```python
BASE / "audit" / "decisions.jsonl"
```

If the file is missing, the function returns an empty list instead of raising.

This makes the reporting module safe to run before the audit directory has any data.

### `volume_mix(records: list[dict]) -> dict`

Summarises rolling business volume.

It calculates:

- total records processed
- counts by binder outcome (`Accept`, `Decline`, `Refer`, etc.)
- counts by broker name
- counts by underwriter ID

Typical output looks like:

```python
{
  "total": 128,
  "by_outcome": {"Accept": 72, "Decline": 29, "Refer": 27},
  "by_broker": {"Acme": 64, "Beta": 41},
  "by_underwriter": {"u1": 80, "u2": 48}
}
```

### `decline_reasons(records: list[dict]) -> dict`

Counts rule-level decline reasons across records.

This inspects each record's `rule_outcomes` and counts rules whose result is `Decline`.

Example output:

```python
{
  "by_rule": {
    "A-002-TIV": 12,
    "A-005-SPRINKLER": 7
  }
}
```

### `override_rate(records: list[dict]) -> dict`

Measures how often a valid decision was overridden by the underwriter and why.

The function:

- filters to records with `decision.valid == True`
- counts records whose action is `override`
- calculates `rate = overrides / decided`
- groups overrides by `reason_code`

Example output:

```python
{
  "decided": 120,
  "overrides": 18,
  "rate": 0.15,
  "by_reason": {
    "BROKER_REQUEST": 9,
    "CAPACITY_PREFERENCE": 5,
    "OTHER": 4
  }
}
```

### `data_quality(records: list[dict]) -> dict`

Surface data-quality problems in the submitted record set.

It tracks:

- missing field counts (`completeness.missing`)
- low-confidence extracted values
- number of `refer_back` actions

This is useful for understanding whether the pipeline is producing weak or incomplete intake data.

Example output:

```python
{
  "missing_fields": {"broker_name": 14, "locations": 6},
  "low_confidence_fields": 8,
  "info_requests": 21
}
```

### `refer_by_field(records: list[dict]) -> dict`

Groups referral reasons by field.

It looks at rule outcomes whose status is `Cannot assess` and records the reason text or rule ID.

Example output:

```python
{
  "by_field": {
    "missing:total_insured_value": 10,
    "missing:broker_name": 4
  }
}
```

### `stage_timing(records: list[dict]) -> dict`

Summarises average stage execution time across records that include `stage_timings`.

This is the implementation for MI-006 and reports:

- mean seconds per stage
- total number of timed records
- a fallback value if no records include timing data

Example output:

```python
{
  "mean_seconds": {
    "extract": 1.8472,
    "derive": 0.3149,
    "review": 2.1043
  },
  "n": 42
}
```

If no stage timings are present, it returns:

```python
{"gap": "no timed records yet"}
```

### `report(path: str | Path | None = None) -> dict`

Convenience function that aggregates all report sections in one call.

It returns a single dictionary with:

- `volume_mix`
- `decline_reasons`
- `override_rate`
- `data_quality`
- `refer_by_field`
- `stage_timing`

This is the most practical entry point for dashboard code and ad hoc report generation.

## Typical usage

```python
from reports.mi import report

summary = report("audit/decisions.jsonl")
print(summary["volume_mix"])
print(summary["override_rate"])
print(summary["data_quality"])
```

Or, if you want to load records and inspect them directly:

```python
from reports.mi import load, volume_mix, decline_reasons, override_rate

records = load("audit/decisions.jsonl")
print(volume_mix(records))
print(decline_reasons(records))
print(override_rate(records))
```

## Data expectations

This module expects decision records to be JSON lines (one JSON object per line), where records may contain fields such as:

- `binder_outcome`
- `decision`
- `rule_outcomes`
- `extracted`
- `extracted_meta`
- `completeness`
- `stage_timings`

The functions are robust to partially populated records because they use `.get(...)` and guard for missing structures.

## Relationship to the wider repository

This folder directly supports the project-level monitoring story in the root README:

- executive MI dashboard uses the audit trail
- volume and outcome reporting are built from JSONL decision records
- underwriter decisions are measured for override behaviour
- operational quality issues are visible via missing-field and low-confidence analysis
- performance gaps can be identified by stage timings

The repository includes tests for this module in:

- `tests/test_mi.py`

Those tests validate the expected logic for:

- outcome mixing
- decline ranking
- override-rate reconciliation
- missing-field detection
- refer-by-field grouping

## Operational notes

- The module is intentionally pure and testable; no network or LLM calls are involved.
- It reads from the runtime `audit/` directory, which is ignored by git and reserved for generated operational records.
- It is safe to call before any audit records exist.
- Missing or incomplete timing data is treated as a reporting gap rather than a fatal error.

## Suggested future enhancements

Potential next steps for this folder include:

1. time-bounded reports (last 7 days / last 30 days / monthly rollups)
2. CSV or JSON export helpers for downstream BI tooling
3. trend comparisons against prior periods
4. richer stage-timing breakdown by binder, underwriter, or submission type
5. dashboard-friendly schemas for UI consumption

## Summary

The `reports` folder is the reporting layer for the Binder Selection Agent. It transforms the system's audit trail into practical, defensible operational metrics without introducing hidden business logic. In short, it turns machine decisions into management insight.

If you are working on the project and need to extend reporting, start with `reports/mi.py` and the corresponding tests in `tests/test_mi.py`.
