# appetite.py — deterministic rules + logic groups

```mermaid
flowchart TD
    A[extracted + ruleset] --> B[evaluate each rule → Pass/Decline/Cannot assess]
    B --> C[combine logic groups]
    C --> C1[ungrouped: pass through]
    C --> C2[AND group: all bite → Decline; any Pass → Pass; else Cannot assess]
    C --> C3[OR group: any bite → Decline]
    C --> C4[location-scoped AND: per-site pairing only]
    C1 --> D{any Decline?}
    C2 --> D
    C3 --> D
    C4 --> D
    D -->|yes| E[Decline]
    D -->|no, any Cannot assess| F[Refer]
    D -->|all Pass| G[Accept]
```

**Business context:** BFR-APP-002 (tri-state), BFR-APP-004 (deterministic, no LLM), BFR 7.4 (logic groups), OPEN-10 (unspecified valuation → Refer, not Decline). Per-site pairing prevents cross-site false positives.
