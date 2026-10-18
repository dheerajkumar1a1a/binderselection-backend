# demo.py — self-resetting end-to-end demo

```mermaid
flowchart TD
    A[main] --> B[wipe audit/ledger/checkpoints]
    B --> C[build graph with checkpointer]
    C --> D[invoke with sample docs]
    D --> E[print extract/completeness/per-binder/rank]
    E --> F[auto-accept as demo underwriter]
    F --> G[print settle + audit + MI]
```

**Business context:** deterministic stub extractor, no API key; demonstrates full gate chain and MI in one command.

## Example run

`python demo.py` wipes audit/ledger/checkpoints, runs SUB-DEMO-001, prints extract→completeness→per-binder (A Accept, B Accept)→rank (A 10.0)→auto-accept→settle (reserved 6.5M)→audit eval-…→MI. Ends with "1 passed" equivalent: 79 tests green.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["wipe state"] --> B["build graph"]
    B --> C["invoke SUB-DEMO-001"]
    C --> D["A Accept, B Accept, rec A"]
    D --> E["auto-accept → settle reserved 6.5M"]
    E --> F["audit + MI printed"]
```
