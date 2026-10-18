# narrative.py — advisory wording only

```mermaid
flowchart TD
    A[state with determined outcomes] --> B[build per-binder lines: eligible / not recommended with bitten rules / needs info]
    B --> C[append recommended binder + score + advisory disclaimer]
    C --> D[narrative string]
```

**Business context:** BFR-REC-007/008/010/011 — describes already-determined outcomes, decides nothing; never says bound/placed; LLM may rephrase but not add conclusions.
