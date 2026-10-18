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

## Example run

binder_A: authorised 15,000,000, written 5,000,000, reserved 0 → available 10,000,000 ≥ TIV 6,500,000 → eligible, snapshot attached. Suspended binder_B (hypothetical): screen_safe returns excluded:suspended-or-retired without touching capacity. Capacity source down: returns failed:... rather than omitting the binder.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["binder_A: auth 15M, written 5M, reserved 0"] --> B["available = 10M"]
    B --> C["10M >= TIV 6.5M → eligible"]
    C --> D["snapshot attached to result"]
```
