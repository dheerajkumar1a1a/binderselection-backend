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
