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
