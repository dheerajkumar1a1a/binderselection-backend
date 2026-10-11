# Leadership demo UI

Business-level working demonstration of the Binder Selection Agent.
Stdlib only — no new dependencies.

## Run it

```powershell
# from the repo root
python ui/app.py
# open http://127.0.0.1:8099
```

Custom port: `python ui/app.py 9000` or `PORT=9000 python ui/app.py`.

## What leadership gets

1. **At a glance** — live binder registry (status, ruleset version, rule
   counts), scoring weights, sample-case count.
2. **Live demo** — pick any of the 20 sample submissions, run the real
   engine (extract → derive → completeness → per-binder evaluate → rank →
   narrative), inspect per-rule outcomes, then record an underwriter
   decision (accept / override with reason code / refer back) and see
   settlement, audit id, and the auditor evidence pack.
3. **Management picture** — volume, outcome mix, decline reasons, override
   rate, data quality, stage timings, computed live from the audit trail.

Default case `demo-accept-full` shows the full happy path (Binder A
Accepts, Binder B Refers on unlicensed geo data — the Refer-never-Pass
doctrine, live). Try `capacity-shortfall` or `tiv-bite` for the guardrails.

## Demo state

- Writes use `UI-` references into `audit/decisions.jsonl` and
  `ui/demo-ledger.json` (both gitignored) so the MI dashboard moves live.
- Fresh start: `python ui/reset_demo.py` reseeds the ledger from
  `rules/capacity.json` and clears UI audit lines.
