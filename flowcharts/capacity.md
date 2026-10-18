# capacity.py — derived capacity screening

```mermaid
flowchart TD
    A[extracted + binder capacity cfg] --> B[screen: available = authorised − written − reserved]
    B --> C{available >= TIV?}
    C -->|yes| D[eligible + snapshot]
    C -->|no| E[excluded: capacity shortfall]
    F[screen_safe] --> G{binder suspended/retired?}
    G -->|yes| H[excluded: suspended-or-retired]
    G -->|no| I{capacity source ok?}
    I -->|fail| J[failed: error]
    I -->|ok| B
```

**Business context:** capacity is derived, never stored (BFR-CAP-002); lifecycle filter (BFR-CAP-003) and source-failure safety (BFR-CAP-012) ensure a binder is never silently omitted.
