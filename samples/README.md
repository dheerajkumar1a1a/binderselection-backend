# Sample dataset for binderselection-backend

This folder contains the reference sample inputs, test fixtures, and research notes used to validate the Binder Selection Agent workflow in this repository.

The samples are intentionally deterministic and device-agnostic: all paths are relative, the files are UTF-8 encoded, and the repo enforces LF line endings. The dataset is designed to exercise the real extraction → completeness → capacity → appetite → ranking pipeline without requiring a live LLM or external secrets.

## Purpose

The `samples/` folder exists to:

- provide repeatable test cases for binder selection logic
- verify rule behavior across accept, decline, refer, and halt paths
- document expected outcomes for realistic and adversarial submissions
- support reproduction of demo runs and QA reviews
- preserve a readable audit trail for sample-driven analysis

This is not just example data; it is part of the validation contract for the application.

## Folder structure

```text
samples/
├── manifest.json
├── DATASET-DEMO-REPORT.md
├── RESEARCH-REPORT.md
├── cases/
│   ├── 01-accept-standard.json
│   ├── 02-tiv-bite.json
│   ├── 03-tiv-boundary.json
│   ├── 04-capacity-shortfall.json
│   ├── 05-capacity-zero.json
│   ├── 06-sprinkler-bite.json
│   ├── 07-sprinkler-mixed.json
│   ├── 08-commodity-cannabis.json
│   ├── 09-commodity-cbd-lower.json
│   ├── 10-missing-commodities-refer.json
│   ├── 11-halt-no-broker.json
│   ├── 12-halt-no-locations.json
│   ├── 13-halt-empty.json
│   ├── 14-currency-string.json
│   ├── 15-sov-four-locations.json
│   ├── 16-loss-single-bite.json
│   ├── 17-valuation-bite.json
│   ├── 18-inception-past-bite.json
│   ├── 19-expiring-disclosed-bite.json
│   └── 20-demo-accept-full.json
└── README.md   <- this file
```

## Files in this folder

### `manifest.json`

This is the coverage map for the sample suite.

It tells you:

- which case file covers which requirement or BFR clause
- the expected behavior for each scenario
- the dataset version and description
- the mapping between case files and business assertions

This file is checked by automated tests to ensure the sample set stays in sync with the repository documentation and code.

### `cases/`

This directory contains the actual submission fixtures used for deterministic testing.

Each case is a JSON document representing a sample submission, typically including:

- a `submission_reference`
- one or more `documents`
- `structured_hint` values used by the stub extractor
- capacity parameters such as `line`, `written`, and `reserved`
- expected gate or rule outcomes used by dataset tests

The cases intentionally cover:

- Accept paths
- Decline paths
- Capacity halts and exclusions
- Missing data and completeness halts
- Currency/formatting normalization
- Multi-location rule evaluation
- Commodity and sprinkler rules
- Derived/aggregate risk logic

### `DATASET-DEMO-REPORT.md`

This summary document explains the shape and intended behavior of the sample dataset, including:

- what each case proves
- the expected outcomes by case number
- the test output from the dataset suite
- a walkthrough of the end-to-end demo behavior

### `RESEARCH-REPORT.md`

This is a deeper analytical report documenting:

- the rules under test
- each case-level autopsy
- cross-case interpretation
- reproduction steps
- known limitations of the sample set and the vertical slice

## Case catalogue

The sample set currently includes 20 cases:

| Case | File | Scenario |
|---|---|---|
| 01 | `01-accept-standard.json` | Standard accept case |
| 02 | `02-tiv-bite.json` | TIV above threshold |
| 03 | `03-tiv-boundary.json` | TIV exactly at threshold |
| 04 | `04-capacity-shortfall.json` | Capacity exclusion with shortfall |
| 05 | `05-capacity-zero.json` | Zero-capacity binder |
| 06 | `06-sprinkler-bite.json` | Unsprinklered site |
| 07 | `07-sprinkler-mixed.json` | Mixed location outcomes |
| 08 | `08-commodity-cannabis.json` | Cannabis exclusion |
| 09 | `09-commodity-cbd-lower.json` | Case-insensitive commodity match |
| 10 | `10-missing-commodities-refer.json` | Missing commodity causes refer |
| 11 | `11-halt-no-broker.json` | Missing broker causes completeness halt |
| 12 | `12-halt-no-locations.json` | Missing location data causes halt |
| 13 | `13-halt-empty.json` | Empty/unparseable input causes halt |
| 14 | `14-currency-string.json` | Currency string normalization |
| 15 | `15-sov-four-locations.json` | Four-location SOV evaluation |
| 16 | `16-loss-single-bite.json` | Single-claim loss rule |
| 17 | `17-valuation-bite.json` | Valuation bite |
| 18 | `18-inception-past-bite.json` | Inception-date bite |
| 19 | `19-expiring-disclosed-bite.json` | Expiring/disclosed rule |
| 20 | `20-demo-accept-full.json` | Full demo accept scenario |

## Typical data shape

Each case is a JSON object similar to:

```json
{
  "submission_reference": "SUB-001",
  "documents": [
    {
      "doc_id": "mail-001",
      "structured_hint": {
        "total_insured_value": "$5,000,000",
        "broker_name": "Acme",
        "locations": [{ "sprinklered": true }],
        "commodities": [{ "commodity_type": "STEEL" }]
      }
    }
  ],
  "capacity": {
    "line": 15000000,
    "written_to_date": 5000000,
    "reserved": 0
  },
  "expected": {
    "outcome": "Accept",
    "recommendation": "binder_A"
  }
}
```

The exact structure may vary by case, but the intent is consistent: a submission is represented in a deterministic, machine-checkable way so that the stack can evaluate it without depending on live APIs or uncontrolled data.

## How to use the sample data

From the repository root:

```powershell
python -m pytest tests/test_dataset.py -v
```

This test suite drives the real code paths through the case files and verifies the expected outcomes.

You may also run the broader suite:

```powershell
python -m pytest tests -q
```

The sample set is designed to verify the project-level pipeline and to catch regressions when rule logic, normalization, or completeness gates change.

## What the sample suite validates

The dataset enforces checks for:

- correct accept / decline / refer / halt behavior
- per-location rule application
- TIV threshold handling, including boundary equality
- commodity normalization and case-insensitive matching
- absence handling for required fields
- money normalization for strings such as `$8,250,000`
- capacity screening before appetite evaluation
- determinism across repeated runs

## Reproducibility notes

The sample tests are intentionally designed to be reproducible:

- no secrets required
- no live LLM required
- no environment-specific absolute paths
- no hidden randomness
- UTF-8 + LF only

This makes the dataset suitable for version control, regression testing, and review by non-technical stakeholders.

## Related project files

The samples folder complements the project README and the core engine files:

- `README.md` — overall architecture and business context
- `tests/test_dataset.py` — dataset runner
- `demo.py` — end-to-end pipeline demonstration
- `rules/` — binder and scoring definitions
- `nodes/` — extraction and evaluation workflow
- `capacity/` — capacity ledger logic

## Summary

`samples/` is the repository's curated decision dataset. It documents expected behavior for normal and edge-case submissions, provides a stable benchmark for automated validation, and acts as a concrete record of the system's current business logic.

If you are debugging a rule, verifying a regression fix, or preparing a demo, start with this folder and the manifest-driven test suite.
