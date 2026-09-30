# Research report — sample dataset, per-sample autopsy, full output (v0.3.0)

- Date: 2026-09-30. Repo `binderselection-backend` (private,
  `github.com/dheerajkumar1a1a/binderselection-backend`), commit `ecc14d5`, tag `v0.3.0`.
- Environment: Windows 11, PowerShell 5.1, Python 3.11.0, pytest 9.1.1,
  langgraph 1.2.11, langchain-core 1.6.3.
- Method: stub extractor (deterministic, no API key) so every number below
  reproduces byte-for-byte. Each case is driven through the real nodes in
  pipeline order — `stub_extract → completeness → capacity (case-owned
  line/written/reserved) → appetite (approved Binder A v1 ruleset) →
  rank` — by `tests/test_dataset.py`. Full JSON traces were dumped with a
  throwaway tracer and every figure quoted here is copied from that output.
- Suite result: **43 passed, 0 failed** (27 unit + 16 dataset: 15 cases +
  manifest-consistency). Demo (`python demo.py`) full loop green, audit
  `eval-7e55f307`, MI reconciled.

## 0. Rules under test (approved Binder A v1, `rules/binder_A_v1.json`)

| rule_id | Category | Logic | Threshold |
|---|---|---|---|
| A-002-TIV | Total Insured Value | `total_insured_value <= 10,000,000` | 10m, currency |
| A-005-SPRINKLER | Construction / COPE, location scope | every `locations[].sprinklered is True` | boolean |
| A-009-COMMODITY | Commodity Rule | no `commodities[].commodity_type` in {CANNABIS, MARIJUANA, CBD, THC} (case-insensitive) | code list |

Aggregation (BFR-APP-004): any Decline → binder Decline; else any
Cannot-assess → Refer; else Accept. Rank placeholder: Accept → score 7.0,
recommend binder_A; anything else → "no eligible binder" (BFR-REC-009).

---

## 1. accept-standard — the control case (Accept → binder_A)

**Story.** Broker Acme Marine Ltd submits a 6.5m steel risk on one sprinklered
warehouse at 12 Port Road. Nothing about it should bite.
**Capacity params.** line 15m, written 5m, reserved 0 → available 10m.
**Extraction.** All four fields present, confidence 1.0, source `mail-001`:
TIV normalised int 6500000 → float 6500000.0 (original kept as 6500000);
broker string; one location `{address 12 Port Road, sprinklered true}`;
one commodity STEEL.
**Completeness.** missing=[] → can_evaluate true.
**Capacity.** 15,000,000 − 5,000,000 − 0 = 10,000,000 ≥ TIV 6,500,000 →
eligible. Snapshot stored with all four legs so the decision stays explicable
after positions move (BFR-CAP-007).
**Appetite.** A-002: 6,500,000 ≤ 10,000,000 → Pass (value recorded).
A-005: per-location values [true], all-true → Pass. A-009: ["STEEL"], upper
"STEEL" ∉ exclusion list → Pass.
**Rank.** Accept → scores {binder_A: 7.0}, ranking [binder_A], recommendation
binder_A.
**Proves.** BFR-APP-002 Pass path, BFR-REC-008 single recommendation with
traceable rationale. This is the shape every other case deviates from.

## 2. tiv-bite — one unit over the cap (Decline)

**Story.** Identical risk but TIV 10,000,001. Capacity deliberately widened
(line 30m, written 0) so the *rule* bites rather than capacity screening —
isolating appetite from capacity, which is exactly why each case owns its
capacity params.
**Extraction.** TIV 10000001 → 10000001.0, rest identical to case 01.
**Capacity.** 30,000,000 available ≥ 10,000,001 → eligible.
**Appetite.** A-002: 10,000,001 ≤ 10,000,000 is false → Decline with the
driving value recorded. A-005 Pass [true]. A-009 Pass ["STEEL"].
Aggregation: one Decline → binder Decline. **Rank.** scores {}, ranking [],
"no eligible binder" with the consolidated reason (BFR-REC-009), not an empty
response.
**Proves.** BFR-APP-002 Decline path; one biting rule vetoes the binder;
underwriter sees which rule bit and the value that bit it (BFR-UWR-002).

## 3. tiv-boundary — exactly 10,000,000 (Accept)

**Story.** The boundary probe the BFR's OPEN-1 complains is undefined
elsewhere: here the operator is `lte`, so equality must pass.
**Capacity.** line 20m, written 5m → available 15m ≥ 10m → eligible.
**Appetite.** A-002: 10,000,000 ≤ 10,000,000 → Pass. Others Pass.
**Rank.** Accept → binder_A 7.0.
**Proves.** Inclusive-boundary semantics are pinned by test; any future
threshold edit that flips this case fails loudly. Also exercises the
BFR-CAP-004 edge (available exactly covers TIV).

## 4. capacity-shortfall — 20m risk, 10m free (excluded, shortfall 10m)

**Story.** A risk the appetite rules would pass, but the facility cannot fit.
**Extraction.** TIV 20000000.0, all fields present.
**Completeness.** Passes — data is fine; money is the problem.
**Capacity.** 15,000,000 − 5,000,000 − 0 = 10,000,000 < 20,000,000 →
`excluded:shortfall=10000000.0`. Pipeline stops here; appetite never runs, so
no rule is half-evaluated on an ineligible binder. Shortfall math asserted
exactly: TIV − available = 10,000,000.0.
**Proves.** BFR-CAP-004 with recorded shortfall; screening precedes appetite;
exclusion reasons are visible to the underwriter (BFR-UWR-001).

## 5. capacity-zero — exhausted facility, tiny risk (excluded)

**Story.** 100k risk — pocket change — against a binder with 15m/15m written.
**Capacity.** available = 0 → `excluded:shortfall=100000.0` (0 is not > 0).
**Proves.** BFR-CAP-003: zero-capacity binders never appear in recommendations
regardless of risk size. Guards the delegated-authority relationship against
the most embarrassing failure mode — recommending a full facility.

## 6. sprinkler-bite — unsprinklered warehouse (Decline)

**Story.** 2m steel risk, single site 7 Dockside, sprinklered=false, sourced
from `sov-001` (SOV document, exercising multi-document provenance).
**Capacity.** 30m free → eligible.
**Appetite.** A-002 Pass (2m). A-005: values [false], all-true fails →
Decline, evidence value [false] stored. A-009 Pass.
**Rank.** Decline → no eligible binder.
**Proves.** BFR-APP-010 location scope; COPE rule bites on the site's own
attribute; provenance points at the SOV, not the email (BFR-EXT-002,
BFR-UWR-003 drill-through).

## 7. sprinkler-mixed — one bad site out of two (Decline)

**Story.** 4m risk across sites A (sprinklered) and B (not).
**Appetite.** A-005 values [true, false] → Decline. The trace preserves the
per-site vector, so the underwriter is told *which* location caused it
(BFR-APP-010 acceptance criterion) — compare with case 06's [false].
**Proves.** Universal quantification over locations; a single non-compliant
site vetoes; evidence distinguishes the mixed case from the uniformly-bad one.

## 8. commodity-cannabis — excluded commodity (Decline)

**Story.** 1m risk, clean site, commodity "Cannabis" (title case as a broker
would type it).
**Appetite.** A-002 Pass, A-005 Pass, A-009: upper("Cannabis")="CANNABIS" ∈
list → Decline, original "Cannabis" preserved in the evidence value.
**Proves.** Commodity exclusion path; original text retained alongside the
match so the underwriter sees what the broker actually wrote.

## 9. commodity-cbd-lower — lowercase "cbd" (Decline)

**Story.** Same shape as 08 but commodity "cbd" — brokers don't normalise case.
**Appetite.** upper("cbd")="CBD" ∈ list → Decline.
**Proves.** Case-insensitive matching pinned; a future refactor that compares
raw strings would let CBD through and this case would catch it. Pairs with 08
as the normalisation-matrix for the commodity rule.

## 10. missing-commodities-refer — absent commodity (Refer, Cannot-assess)

**Story.** 1m clean risk, broker + site + TIV present, commodity never stated.
**Extraction.** commodities=None; meta `{present: false, confidence: 0.0,
reason: absent}` — no inference, no default (BFR-EXT-003).
**Completeness.** Passes (commodities is not in the mandatory set) — the case
reaches appetite, which is the point: this tests rule-level missing data, not
intake gating.
**Appetite.** A-002 Pass, A-005 Pass, A-009: value None → Cannot-assess with
reason `missing:commodities.commodity_type` naming the exact absent field.
Aggregation: no Decline + one Cannot-assess → binder Refer.
**Rank.** Refer → no eligible binder (rank only scores Accepts).
**Proves.** The load-bearing safety property BFR-APP-003: Cannot-assess is
never treated as Pass. The old prototype's shared prompt skipped
data-absent rules (an Accept by omission); this case would have caught that
regression. It also documents OPEN-10: Binder E declines on missing data
while others refer — the target behaviour encoded here is refer.

## 11. halt-no-broker — broker absent (halt at completeness)

**Story.** Site + TIV present, broker never named.
**Extraction.** broker_name=None, meta absent/0.0.
**Completeness.** missing=[broker_name] → can_evaluate false. Pipeline stops;
capacity and appetite never execute — there is no capacity snapshot and no
rule outcome in the trace, which is itself asserted.
**Proves.** Intake gating precedes evaluation; the RFI names the field
(BFR-UWR-008 input); nothing is evaluated on unidentified submissions.

## 12. halt-no-locations — no schedule of values (halt at completeness)

**Story.** Broker + TIV present, no sites at all.
**Completeness.** missing=[locations] → halt.
**Proves.** SOV-less submissions cannot reach location-scoped rules; pairs
with 11 to show each mandatory field gates independently.

## 13. halt-empty — unparseable scan (halt, all mandatory missing)

**Story.** One document, free text "Scanned image, unparseable", no hints —
the OCR-failure / corrupt-file shape (BFR-SUB-005/008).
**Extraction.** All four fields None, all meta absent/0.0. Nothing invented.
**Completeness.** missing=[total_insured_value, broker_name, locations] in
mandatory order → halt.
**Proves.** BFR-SUB-005: the document is never silently discarded — it yields
an explicit all-absent record and a named-missing halt, visible to Operations
and the underwriter. (Process note: this case caught a bug in its own
expectation file — wrong missing-order — before push. The suite tests the
tests.)

## 14. currency-string — "$8,250,000" as written (Accept)

**Story.** Broker writes the TIV as a dollar string, as brokers do.
**Extraction.** `_norm_money("$8,250,000")` → value 8250000.0,
original_value "$8,250,000" preserved (BFR-EXT-008). Meta present/1.0.
**Appetite.** A-002: 8,250,000 ≤ 10,000,000 → Pass on the normalised value;
the original string remains citable in evidence.
**Rank.** Accept → binder_A.
**Proves.** Unit/currency normalisation with original-value retention; the
comparison runs on numbers while the audit shows what the broker wrote.

## 15. sov-four-locations — four-site SOV (Accept)

**Story.** 9m risk across four sprinklered sites A–D.
**Appetite.** A-002 Pass (9m). A-005 values [true, true, true, true] → Pass.
A-009 Pass.
**Rank.** Accept → binder_A 7.0.
**Proves.** BFR-EXT-005: the schedule is a repeating structure, not an
aggregate — four location records, each independently attributed, evaluated
as a vector. The trace's four-element evidence array is the shape the
underwriter drills into per BFR-UWR-002.

---

## 16. Cross-case readings

- **Halt ladder.** 3 halts at completeness (11–13) + 2 exclusions at capacity
  (04–05) + 10 full evaluations: each gate's population is covered, and no
  halted case carries downstream artefacts (no phantom rule outcomes).
- **Outcome census.** Accept 3 (01, 03, 14, 15 — four), Decline 5 (02, 06,
  07, 08, 09), Refer 1 (10), completeness-halt 3, capacity-halt 2. Every
  BFR-APP-002 outcome and every pipeline exit appears at least once.
- **Rule census.** Each rule shows Pass (01), Decline (02 / 06–07 / 08–09),
  and A-009 shows Cannot-assess (10) — the per-rule bite/non-bite/unassessable
  matrix BFR §14 demands for `BFR-APP` verification.
- **Determinism spot-check.** Re-running the tracer reproduces every figure;
  the suite asserts exact shortfall arithmetic (10,000,000.0) and exact
  missing-field lists, so nondeterminism or silent schema drift fails loudly.
- **What the set does NOT cover (explicit gaps).** Live-LLM extraction
  variance (stub only here; live path verified separately, commit `409789e`);
  binders B–E and the other 40 Appendix-A rules; multi-binder ranking and
  tie-breaks (OPEN-2/5); reservation interplay under evaluation
  (covered separately in `test_settle.py`); auth, concurrency, timing
  (BFR-NFR, README §10–12).

## 17. Reproduce

```powershell
git clone https://github.com/dheerajkumar1a1a/binderselection-backend.git
cd binderselection-backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest tests/test_dataset.py -v   # 16/16, case names listed
python -m pytest tests -q                    # 43/43
python demo.py                               # full loop, self-resetting
```

Dataset: `samples/cases/01..15`, coverage map `samples/manifest.json`,
runner `tests/test_dataset.py`, demo `demo.py`, method note
`samples/DATASET-DEMO-REPORT.md`.
