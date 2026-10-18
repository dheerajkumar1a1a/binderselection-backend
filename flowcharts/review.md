# review.py — human decision gate

```mermaid
flowchart TD
    A[state] --> B[interrupt question]
    B --> C[underwriter responds]
    C --> D{action}
    D -->|accept| E[validate: recommendation eligible?]
    D -->|override| F[validate: reason_code required, no hard-decline]
    D -->|refer_back| G[info request list]
    D -->|correct| H[apply corrections, re-evaluate]
    E --> I[decision recorded with identity+timestamp]
    F --> I
    G --> I
    H --> I
```

**Business context:** underwriter decides, system only recommends (BFR 2.4, BFR-UWR); override needs reason code (BFR-UWR-005); hard-decline selection blocked (BFR-UWR-007); identity + timestamp (BFR-UWR-006); correct triggers re-evaluation (BFR-EXT-006/007).

## Example run

Underwriter sends `{action:"accept", underwriter_id:"demo-underwriter"}`. validate checks recommendation eligible → valid. decision recorded with identity + timestamp. Underwriter sends `{action:"correct", corrections:{total_insured_value:5000000}}` → graph routes back to derive and re-evaluates; decision recorded with corrections.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["interrupt: recommendation binder_A"] --> B["underwriter sends accept"]
    B --> C["validate: eligible → valid"]
    C --> D["decision recorded: demo-underwriter, timestamp"]
```
