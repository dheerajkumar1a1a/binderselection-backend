# state.py — submission state contract

```mermaid
flowchart LR
    S[SubmissionState] --> F1[submission_reference]
    S --> F2[documents]
    S --> F3[extracted / extracted_meta]
    S --> F4[completeness]
    S --> F5[binder_results / rulesets]
    S --> F6[scores / ranking / recommendation]
    S --> F7[narrative]
    S --> F8[decision]
    S --> F9[settlement]
    S --> F10[stage_timings / model_versions]
    S --> F11[supersedes / audit_id]
```

**Business context:** single typed contract shared by every node; carries extracted risk data, per-binder outcomes, cross-binder ranking, underwriter decision, settlement, audit linkage, timings and model versions. `supersedes` links re-evaluations to the original record (BFR-AUD-004).

## Example run

State after step 3 for SUB-DEMO-001:
- `submission_reference` = "SUB-DEMO-001"
- `extracted` = {total_insured_value: 6500000.0, broker_name: "Acme Marine Ltd.", locations: [{...}], ...}
- `extracted_meta` = {total_insured_value: {value, confidence:1.0, source_document_id:"mail-001", ...}}
- `completeness` = {missing: [], can_evaluate: true}
- `binder_results`, `scores`, `narrative`, `decision`, `settlement` populated in later steps
