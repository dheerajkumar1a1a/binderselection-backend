# completeness.py — mandatory + contested gate

```mermaid
flowchart TD
    A[extracted + meta] --> B[mandatory = TIV, broker, locations]
    B --> C{any missing?}
    C -->|yes| D[missing list, can_evaluate false]
    C -->|no| E[contested list from meta]
    E --> F[can_evaluate true, contested flagged]
    D --> G[graph routes to refer-back]
    F --> G2[graph routes to evaluate]
```

**Business context:** BFR-APP-003 — missing mandatory data → Refer, never Pass. Contested fields surface to the underwriter rather than being silently resolved.
