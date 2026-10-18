# derive.py — derived aggregates and flags

```mermaid
flowchart TD
    A[extracted] --> B[loss aggregates: largest single claim, total claims]
    B --> C[insured_in_continental_us flag]
    C --> D[years_trading from business_commencement_date]
    D --> E[return derived fields merged into extracted]
```

**Business context:** derived fields are computed, never stored (BFR 7.1.6); capacity is likewise derived (BFR-CAP-002). Rules reference derived fields by name.

## Example run

Input extracted: total_insured_value 6500000, largest_single_claim_amount 0, total_claims_amount 0, business_commencement_date "2020-01-01", insured_in_continental_us true.
Output adds: largest_single_claim_amount=0 (already), total_claims_amount=0, insured_in_continental_us=true, years_trading=6 (as of eval date). Rules A-003a/b and A-004 now have real values to evaluate against.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["extracted: TIV 6.5M, claims 0/0, commencement 2020-01-01, continental US true"] --> B["loss aggregates: largest 0, total 0"]
    B --> C["insured_in_continental_us = true"]
    C --> D["years_trading = 6"]
    D --> E["merged into extracted"]
```
