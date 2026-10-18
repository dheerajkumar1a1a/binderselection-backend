# multibind.py — per-binder eval + absolute ranking

```mermaid
flowchart TD
    A[extracted] --> B[for each active binder]
    B --> C[capacity screen_safe]
    C -->|not eligible| D[excluded/failed result]
    C -->|eligible| E[load_effective ruleset]
    E --> F[appetite._evaluate_rules]
    F --> G[binder result]
    D --> H[collect results]
    G --> H
    H --> I[score_binders]
    I --> I1[only Accept binders scored]
    I1 --> I2[parts: capacity + strategic + appetite]
    I2 --> I3[sort by total then tie_break config]
    I3 --> J[ranking + recommendation]
```

**Business context:** binders are data, not agents (BFR-APP-011); scoring absolute, not relative (BFR-REC-005); tie-break configured (BFR-REC-006, OPEN-5). Removing a binder does not change others' scores.

## Example run

evaluate_binders on clean submission: binder_A Accept (all 9 pass), binder_B Accept (all 7 pass) — both eligible. score_binders: A 5+2+3=10.0 (preferred), B 5+0+3=8.0 (standard). ranking [binder_A, binder_B], recommendation binder_A. Removing binder_B from the list leaves A's score unchanged (absolute scoring).
