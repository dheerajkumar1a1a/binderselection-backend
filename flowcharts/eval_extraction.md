# scripts/eval_extraction.py — nightly extraction eval

```mermaid
flowchart TD
    A[fixtures] --> B[run extraction]
    B --> C[score against expected]
    C --> D[gate pass/fail]
```

**Business context:** nightly Nemotron extraction eval gate consuming repo secret.

## Example run

Nightly workflow runs `scripts/eval_extraction.py` against Nemotron on the 25 fixtures, scores field-level extraction, fails the gate if below threshold. Uses repo secret for API key.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["nightly run"] --> B["Nemotron on 25 fixtures"]
    B --> C["score field-level"]
    C --> D["gate pass/fail"]
```
