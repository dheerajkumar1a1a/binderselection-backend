# settle.py — capacity reservation / release

```mermaid
flowchart TD
    A[decision] --> B{action}
    B -->|accept/override selected binder| C[reserve capacity for selected binder]
    B -->|refer_back| D[release any prior reservation]
    C --> E[ledger: reserve idempotent]
    D --> E
    E --> F[settlement record]
```

**Business context:** BFR-CAP-008/009 — bind only on underwriter decision; idempotent reservation prevents double-counting.

## Example run

decision accept binder_A: reserve 6,500,000 → ledger available 10,000,000 → 3,500,000, reservation_id res-17010f98, deduped false. decision refer_back: release prior reservation, available restored.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["decision accept binder_A"] --> B["reserve 6.5M"]
    B --> C["available 10M → 3.5M"]
    C --> D["reservation_id res-17010f98, deduped false"]
    D --> E["settlement {action:reserved}"]
```
