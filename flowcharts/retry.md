# retry.py — bounded backoff

```mermaid
flowchart TD
    A[fn] --> B{attempt}
    B --> C[call fn]
    C -->|success| D[return]
    C -->|transient error 429/5xx/URLError| E{retries left?}
    E -->|yes| F[sleep base*2^attempt]
    F --> B
    E -->|no| G[raise]
    C -->|non-transient| G
```

**Business context:** NFR-016 — transient failures retried with backoff; non-transient fail fast; blast radius bounded.

## Example run

OpenRouter returns 429 twice then 200: with_retry calls fn 3 times, sleeping 0.5s then 1.0s, returns the 200 payload. A 400 (non-transient) raises immediately on first attempt.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["OpenRouter call"] --> B["429 → sleep 0.5s"]
    B --> C["429 → sleep 1.0s"]
    C --> D["200 → return payload"]
```
