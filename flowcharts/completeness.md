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

## Example run

Case 10 (missing commodities): extracted has TIV, broker, locations → mandatory ok, can_evaluate true, but commodity absent means A-009 Cannot assess → binder Refer. Contested case (two docs disagree on TIV): completeness.contested=["total_insured_value"], surfaced to underwriter, not silently resolved.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["extracted: TIV, broker, locations present"] --> B["mandatory check: none missing"]
    B --> C["contested check: none"]
    C --> D["can_evaluate = true → route to evaluate"]
```
