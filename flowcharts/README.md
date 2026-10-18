# Flowcharts index

One mermaid flowchart per source file, each keeping the **business high-level context** (BFR clauses, invariants) alongside the code flow. Rendered natively by GitHub in any `.md` file.

| File | Source | Business focus |
|---|---|---|
| [graph.md](graph.md) | `graph.py` | full gate chain + correction loop |
| [state.md](state.md) | `state.py` | submission state contract |
| [persistence.md](persistence.md) | `persistence.py` | audit + evidence pack + supersession |
| [extract.md](extract.md) | `nodes/extract.py` | document → risk data, confidence, provenance |
| [extract_openrouter.md](extract_openrouter.md) | `nodes/extract_openrouter.py` | live LLM extraction (OpenRouter) |
| [extract_nvidia.md](extract_nvidia.md) | `nodes/extract_nvidia.py` | live LLM extraction (NVIDIA Nemotron) |
| [derive.md](derive.md) | `nodes/derive.py` | derived aggregates/flags |
| [completeness.md](completeness.md) | `nodes/completeness.py` | mandatory + contested → Refer |
| [capacity.md](capacity.md) | `nodes/capacity.py` | derived capacity screening |
| [appetite.md](appetite.md) | `nodes/appetite.py` | deterministic rules + logic groups |
| [multibind.md](multibind.md) | `nodes/multibind.py` | per-binder eval + absolute ranking |
| [rank.md](rank.md) | `nodes/rank.py` | scoring wrapper |
| [review.md](review.md) | `nodes/review.py` | human decision gate |
| [correct.md](correct.md) | `nodes/correct.py` | correction + re-evaluation trail |
| [settle.md](settle.md) | `nodes/settle.py` | capacity reservation/release |
| [narrative.md](narrative.md) | `nodes/narrative.py` | advisory wording only |
| [timing.md](timing.md) | `nodes/timing.py` | stage durations (MI-006) |
| [retry.md](retry.md) | `nodes/retry.py` | bounded backoff |
| [log.md](log.md) | `nodes/log.py` | content-redacting logs |
| [parse.md](parse.md) | `nodes/parse.py` | document parsing (5 formats) |
| [ledger.md](ledger.md) | `capacity/ledger.py` | idempotent reservation ledger |
| [store.md](store.md) | `rules/store.py` | rule versioning/four-eyes/dry-run |
| [mi.md](mi.md) | `reports/mi.py` | MI reports |
| [demo.md](demo.md) | `demo.py` | self-resetting end-to-end demo |
| [ui_app.md](ui_app.md) | `ui/app.py` | local UI |
| [ui_reset_demo.md](ui_reset_demo.md) | `ui/reset_demo.py` | demo reset |
| [gen_parse_fixtures.md](gen_parse_fixtures.md) | `scripts/gen_parse_fixtures.py` | fixture generator |
| [eval_extraction.md](eval_extraction.md) | `scripts/eval_extraction.py` | nightly extraction eval |

Invariants (apply to all): missing data → Refer, never Pass; capacity derived, never stored; scoring absolute, not relative; binders are data not agents; underwriter decides.
