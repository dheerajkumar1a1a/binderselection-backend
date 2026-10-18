# derive.py — derived aggregates and flags

```mermaid
flowchart TD
    A[extracted] --> B[loss aggregates: largest single claim, total claims]
    B --> C[insured_in_continental_us flag]
    C --> D[years_trading from business_commencement_date]
    D --> E[return derived fields merged into extracted]
```

**Business context:** derived fields are computed, never stored (BFR 7.1.6); capacity is likewise derived (BFR-CAP-002). Rules reference derived fields by name.
