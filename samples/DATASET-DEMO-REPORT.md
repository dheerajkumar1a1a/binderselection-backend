# Dataset demo report — sample set + full-loop run (v0.3.0)

- Date: 2026-09-30. Repo: `binderselection-backend`, private,
  `github.com/dheerajkumar1a1a/binderselection-backend`, commit `ecc14d5`, tag `v0.3.0`.
- Environment: Windows 11, PowerShell 5.1, Python 3.11.0, pytest 9.1.1,
  langgraph 1.2.11. Stub extractor (no API key) so every run is deterministic.
- Question answered: does the prototype behave correctly on realistic,
  adversarial, and broken submissions — and can anyone reproduce it on any machine?

## 1. What the dataset is

`samples/cases/` — 15 JSON files, one submission each. Every file carries its own
`documents` (with `structured_hint` extraction input), its own capacity
parameters (`line/written/reserved`), and its `expected` gate outcome.
`samples/manifest.json` maps each case to the BFR clause it proves.
No absolute paths, no secrets, UTF-8, LF enforced by `.gitattributes`.

| # | Case | Story (input) | Expected output |
|---|---|---|---|
| 01 | accept-standard | Steel risk, TIV 6.5m, sprinklered site, capacity 15m/5m | Accept → recommend binder_A, all 3 rules Pass |
| 02 | tiv-bite | TIV 10,000,001 (one unit over cap), wide capacity so the rule itself bites | Decline on A-002-TIV → "no eligible binder" |
| 03 | tiv-boundary | TIV exactly 10,000,000 | Pass (`lte` is inclusive) → Accept |
| 04 | capacity-shortfall | TIV 20m vs 10m available | Excluded before appetite, shortfall recorded = 10,000,000 |
| 05 | capacity-zero | Fully written facility (15m/15m), tiny 100k risk | Excluded, never recommended (BFR-CAP-003) |
| 06 | sprinkler-bite | Unsprinklered warehouse | Decline on A-005-SPRINKLER |
| 07 | sprinkler-mixed | Two sites, one unsprinklered | Decline — a single location bites (BFR-APP-010) |
| 08 | commodity-cannabis | Cannabis shipment | Decline on A-009-COMMODITY |
| 09 | commodity-cbd-lower | Lowercase "cbd" | Decline — matching is case-insensitive |
| 10 | missing-commodities-refer | No commodity stated | Cannot-assess → binder Refer, never a silent Pass (BFR-APP-003) |
| 11 | halt-no-broker | Broker name absent | Halt at completeness, missing=[broker_name], nothing evaluated |
| 12 | halt-no-locations | No schedule of values | Halt at completeness, missing=[locations] |
| 13 | halt-empty | Unparseable scan, no usable data | Halt, all three mandatory fields listed |
| 14 | currency-string | TIV written as "$8,250,000" | Normalised to 8250000.0, original kept, Pass (BFR-EXT-008) |
| 15 | sov-four-locations | Four sprinklered sites, TIV 9m | Each site evaluated independently → Accept |

## 2. How each case is executed

`tests/test_dataset.py` pushes every case through the real nodes in order —
`stub_extract → completeness → capacity (case params) → appetite (approved
Binder A v1 rules) → rank` — and asserts the halt point, the binder outcome,
the recommendation, each named rule outcome, and (for the shortfall case) the
exact shortfall arithmetic. A 16th test asserts the manifest lists exactly the
files on disk, so cases can never drift out of documentation.

## 3. Output: dataset suite 16/16

```
test_case[01-accept-standard] PASSED
test_case[02-tiv-bite] PASSED
test_case[03-tiv-boundary] PASSED
test_case[04-capacity-shortfall] PASSED
test_case[05-capacity-zero] PASSED
test_case[06-sprinkler-bite] PASSED
test_case[07-sprinkler-mixed] PASSED
test_case[08-commodity-cannabis] PASSED
test_case[09-commodity-cbd-lower] PASSED
test_case[10-missing-commodities-refer] PASSED
test_case[11-halt-no-broker] PASSED
test_case[12-halt-no-locations] PASSED
test_case[13-halt-empty] PASSED
test_case[14-currency-string] PASSED
test_case[15-sov-four-locations] PASSED
test_manifest_covers_all_cases PASSED
16 passed in 0.12s
```

Full suite: **43 passed** (27 unit + 16 dataset), zero failures.

## 4. Output: end-to-end demo (`python demo.py`, case-01 shape)

```
1. INTAKE: SUB-DEMO-001, 2 docs → graph pauses at review
2. EXTRACT: TIV 6500000.0 (1.0, mail-001) · broker Acme Marine Ltd. (1.0)
   locations [{12 Port Road, sprinklered}] · commodities [{STEEL}]
3. COMPLETENESS: no gaps → can_evaluate True
4. CAPACITY: 15m line − 5m written = 10m available ≥ 6.5m → eligible
5. APPETITE: A-002-TIV Pass · A-005-SPRINKLER Pass · A-009-COMMODITY Pass
6. RANK: binder_A 7.0 → recommended binder_A
7. REVIEW: demo-underwriter accepts (identity + timestamp recorded)
8. SETTLE: reserved res-9d0021f3, available 10m → 8.5m
9. AUDIT: eval-7e55f307 (immutable JSONL)
10. MI: volume 1 Accept · broker Acme 1 · underwriter demo 1 · overrides 0
```

## 5. Reading of the results

- The happy path works top to bottom: extract with provenance, capacity math,
  unanimous Pass, absolute score, human accept, reservation write-down,
  immutable audit, reconciling MI.
- The guardrails hold where it matters: over-cap TIV declines; missing data
  refers or halts instead of passing; an exhausted binder is excluded even for
  a tiny risk; one bad site out of many still bites; exclusions match
  regardless of capitalisation; dollar-strings normalise without losing the
  original text.
- The suite already paid for itself once: case 13 caught a wrong
  missing-field order in its own expectation file before push.
- Honest limits: stub extractor (live OpenRouter path verified separately,
  commit `409789e`); one binder and three rules (full 43-rule migration is
  OPEN); file-backed ledger (single process — Postgres locking needed for
  concurrent writers); no auth/UI (see README §10–12).

## 6. Reproduce (any machine)

```powershell
git clone https://github.com/dheerajkumar1a1a/binderselection-backend.git
cd binderselection-backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest tests/test_dataset.py -v   # 16/16 with case names
python -m pytest tests -q                    # 43/43
python demo.py                               # full loop, self-resetting
```
