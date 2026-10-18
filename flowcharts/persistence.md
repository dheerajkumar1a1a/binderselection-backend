# persistence.py — audit, evidence pack, supersession

```mermaid
flowchart TD
    A[write_audit state] --> B[build record: submission, extracted_meta, binder_results, decision, settlement, narrative, timings, models, supersedes]
    B --> C[append to audit/decisions.jsonl]
    C --> D[return audit_id = evaluation_id]
    E[evidence_pack record] --> F[single human-readable pack: values, binder outcomes, rules, decision, settlement, models, timings, supersession]
```

**Business context:** immutable audit record per evaluation (BFR-AUD-001/002); re-evaluations leave the original intact and link via `supersedes` (BFR-AUD-004); evidence pack is the single artefact for review (BFR-AUD-008). No secrets or absolute paths stored.
