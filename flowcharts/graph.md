# graph.py — full gate chain

```mermaid
flowchart TD
    A[extract] --> B[derive]
    B --> C[completeness]
    C -->|missing/contested| RFI[refer back: info request → END]
    C -->|sufficient| D[evaluate]
    D --> D1[per-binder capacity screen]
    D1 -->|excluded| X[binder dropped with reason]
    D1 -->|eligible| D2[per-binder appetite rules]
    D2 --> E[rank: absolute scoring + tie-break]
    E --> N[narrative: advisory wording]
    N --> F[review: interrupt]
    F -->|correct| B
    F -->|accept/override/refer_back| G[settle]
    G --> H[audit]
```

**Business context (BFR):** full pipeline BFR §5.1; completeness gate BFR-APP-003 (Refer, never Pass); capacity BFR-CAP-002 (derived); appetite BFR-APP-004/005 (deterministic); rank BFR-REC-003/005/006 (absolute); review BFR-UWR (human decides); settle BFR-CAP-008/009; audit BFR-AUD. Correction loop returns to derive so re-evaluation re-runs every gate.
