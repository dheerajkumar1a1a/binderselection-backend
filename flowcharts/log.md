# log.py — content-redacting logs

```mermaid
flowchart TD
    A[event + fields] --> B[redact blocked keys: text, documents, extracted, value, ...]
    B --> C[JSON line output]
```

**Business context:** NFR-003/024 — structured logs never carry submission content.

## Example run

safe_event("extracted", submission_reference="S", text="secret policy text", value=123, outcome="Accept") → '{"event":"extracted","submission_reference":"S","text":"[redacted]","value":"[redacted]","outcome":"Accept"}'.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["safe_event extracted, text=secret, value=123"] --> B["redact text,value"]
    B --> C["JSON line with [redacted]"]
```
