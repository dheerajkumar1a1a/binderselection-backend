# Binder Selection Backend Test Suite

This folder contains the automated validation suite for the `binderselection-backend` project. The tests exercise the deterministic decision pipeline that turns inbound insurance submissions into structured risk data, checks completeness, applies binder capacity and appetite rules, ranks eligible binders, and records human review and audit outcomes.

The tests are intended to protect the core design goals of the repository:

- deterministic business logic with no hidden AI decision-making
- explicit provenance and missing-data handling
- rule evaluation from versioned JSON definitions
- capacity and lifecycle guardrails
- auditability and evidence capture
- human review + correction workflows

---

## Purpose of the suite

The repository is centered around a decision-support flow for binder selection. The test suite verifies that this flow behaves correctly across the main business paths:

1. extraction and normalization of incoming document data
2. derivation of computed risk fields
3. completeness gating for mandatory submission data
4. capacity screening and binder eligibility checks
5. appetite/rule evaluation against binder-specific rules
6. ranking and recommendation logic
7. narrative generation for human-readable summaries
8. review/override/refer-back enforcement for underwriters
9. settlement and audit persistence
10. regression protection for rule admin and resilience scenarios

In short, these tests ensure the system remains explainable, reproducible, and safe even as rules and data evolve.

---

## Folder structure

```text
tests/
├── __init__.py
├── test_admin.py
├── test_capacity_guards.py
├── test_correct.py
├── test_dataset.py
├── test_derive.py
├── test_evidence.py
├── test_extract.py
├── test_mi.py
├── test_multibind.py
├── test_narrative.py
├── test_openrouter.py
├── test_resilience.py
├── test_review.py
├── test_rules.py
├── test_settle.py
├── test_v2_rules.py
└── README.md   <-- this file
```

---

## How to run the tests

From the repository root:

```bash
python -m pytest tests -q
```

Run a specific file:

```bash
python -m pytest tests/test_extract.py -q
python -m pytest tests/test_dataset.py -q
python -m pytest tests/test_review.py -q
```

Run a subset by keyword:

```bash
python -m pytest tests -k "capacity or review" -q
```

The project is built around a Python 3.11 environment and is expected to run with the dependencies in `requirements.txt`.

---

## Test-by-test overview

### `test_rules.py`

Focus: per-rule pass / fail / cannot-assess behavior.

Covers:
- a rule that passes when the condition is within threshold
- a rule that declines when it exceeds threshold
- a rule result marked `Cannot assess` when required data is missing

This file validates the low-level semantics used throughout binder evaluation.

### `test_extract.py`

Focus: extraction envelope and value normalization.

Covers:
- absent values staying absent rather than being guessed
- money normalization such as `$5,000,000` becoming `5000000.0`
- provenance metadata tracking source document and original value

This is a foundational test for the extraction layer and the requirement to keep evidence with the output.

### `test_derive.py`

Focus: derived fields from raw submission data.

Covers:
- loss aggregates such as largest single claim and total claims
- claim-count windows (3-year and 5-year windows)
- continental-US derivation from country and state/province fields
- years trading derived from business commencement date

This protects the rule-evaluation pipeline from missing or computed business fields.

### `test_correct.py`

Focus: conflicting values and human correction.

Covers:
- detecting contested values across multiple documents
- clearing conflict metadata after a valid underwriter correction
- ensuring a correction updates extracted values and preserves prior evidence
- validating the `correct` review action
- verifying that a correction can flip an evaluation from decline to accept

This test set is essential for replayability and human-in-the-loop correction workflows.

### `test_admin.py`

Focus: rule administration and lifecycle controls.

Covers:
- rejection of invalid fields/operators in rules
- effective version loading for dated rulesets
- four-eyes approval flow for proposals
- dry-run impact analysis before approval
- lifecycle filtering of suspended binders

This protects the governance and versioning behavior of the rules engine.

### `test_capacity_guards.py`

Focus: lifecycle gating and source-failure safety.

Covers:
- active binders remaining eligible
- suspended binders being excluded with a clear failure reason
- unknown binders never being silently accepted

This guards the capacity layer against invalid or stale binder states.

### `test_dataset.py`

Focus: scenario-based evaluation across sample cases.

Covers:
- end-to-end execution of each sample JSON case under `samples/cases/`
- manifest consistency between the dataset manifest and actual file set
- gate behavior for the full decision pipeline: completeness, capacity, appetite, ranking

This is one of the most important regression tests because it validates a broad set of realistic decision paths in a single loop.

### `test_review.py`

Focus: underwriter review logic and business controls.

Covers:
- valid accept decisions
- override requiring reason codes and valid justification
- blocking hard-decline outcomes from invalid override paths
- refer-back flow returning completeness / cannot-assess information

This ensures the human decision layer cannot be bypassed or misused.

### `test_resilience.py`

Focus: retry behavior and safe logging.

Covers:
- retrying transient failures while capping blast radius
- immediate failure for non-transient exceptions
- exhaustion re-raising when retries are exhausted
- redaction of sensitive content from structured logs

This protects the system from brittle downstream failures and secret leakage.

### `test_evidence.py`

Focus: timing, evidence packaging, and audit metadata.

Covers:
- stage timing measurement
- model version recording for the extraction layer
- evidence pack assembly with all sections populated
- aggregate timing metrics for MI / reporting
- audit persistence and supersession linkage

This file ties execution to auditable, traceable state.

### `test_derive.py`

Already described above; it verifies rule-critical derived metrics used downstream.

### `test_multibind.py`

Focus: multi-binder evaluation and ranking.

Covers:
- active binder selection across multiple binder options
- rule evaluation per binder
- ranking, recommendation, and decision selection behavior

This file is central to the cross-binder comparison logic.

### `test_narrative.py`

Focus: narrative generation from deterministic results.

Covers:
- converting structured decision outputs into readable narrative text
- ensuring narrative remains faithful to evaluated outcomes
- preserving explicit reasoning without inventing unsupported conclusions

This keeps the human-facing explanation aligned with the underlying decision data.

### `test_openrouter.py`

Focus: live extraction integration path.

Covers:
- OpenRouter hook behavior and output validation
- model response parsing and schema enforcement
- handling of missing or invalid live-extraction responses

This file validates the optional live LLM integration while preserving the same contract as the stub extraction path.

### `test_mi.py`

Focus: management information and reporting metrics.

Covers:
- stage timing reporting
- report generation from historical decision records
- summarization of observed outcomes and timings

This supports operational monitoring and performance reporting.

### `test_settle.py`

Focus: final state transition after a decision.

Covers:
- accept/override settlement logic
- refer-back cleanup behavior
- release/reservation handling after a decision is finalized

This ensures the workflow does not leave the capacity ledger in a stale or inconsistent state.

### `test_v2_rules.py`

Focus: version 2 rule-set behavior and evolution.

Covers:
- compatibility with newer ruleset definitions
- validation of changed rules and thresholds
- support for versioned rule execution as the rules engine evolves

This acts as a guardrail for future ruleset migrations and policy updates.

---

## Test philosophy

The tests are not simply examples; they are a contract for the business behavior. They intentionally validate the following principles:

- no silent defaults: missing values do not become pass conditions
- no hidden LLM decisions: business outcomes are evaluated by deterministic Python logic
- no untracked provenance: extracted values and their sources remain visible
- no unsafe underwriter actions: override and correction flows are validated
- no unbounded retries: transient errors are retried, but only within strict limits
- no secret leakage: structured logs redact sensitive content

A change in system behavior should usually require a corresponding change in tests.

---

## Coverage areas this suite protects

The test suite covers the major subsystems in this repository:

- `nodes/extract.py` and live extraction hooks
- `nodes/derive.py`
- `nodes/completeness.py`
- `nodes/capacity.py`
- `nodes/appetite.py`
- `nodes/multibind.py` and ranking logic
- `nodes/narrative.py`
- `nodes/review.py` and `nodes/correct.py`
- `nodes/settle.py`
- `rules/store.py` and versioned rulesets
- `capacity/ledger.py`
- `persistence.py` and evidence/audit records

---

## Recommended workflow for contributors

When making changes in the decision pipeline:

1. run the focused test for the area modified
2. run the broader suite when changing shared contracts or state shapes
3. update expected outputs only if the business logic truly changed
4. keep evidence and provenance tests intact when auditing or extraction logic is updated
5. preserve deterministic behavior and human-review safeguards

Example:

```bash
python -m pytest tests/test_extract.py -q
python -m pytest tests/test_review.py -q
python -m pytest tests -q
```

---

## Summary

This folder is the verification backbone of the Binder Selection Agent. It validates the logic that decides whether a submission is complete, how much capacity is available, which binder rules apply, what outcome is recommended, and what evidence is preserved for human review and audit.

If a rule, extraction path, or review workflow changes, the tests in this directory are the first line of protection against silent regressions.

---

## Related repository documents

- `README.md` — project overview and system design
- `nodes/README.md` — workflow node documentation
- `capacity/README.md` — capacity ledger and accounting logic
- `samples/README.md` — sample dataset and case definitions
- `ui/README.md` — business-facing demo interface
