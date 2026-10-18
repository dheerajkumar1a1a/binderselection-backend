# extract_openrouter.py — live LLM extraction (OpenRouter)

```mermaid
flowchart TD
    A[documents] --> B[build prompt + doc text]
    B --> C[POST OpenRouter chat completions]
    C --> D[with_retry: 429/5xx backoff]
    D --> E[parse JSON content]
    E --> F[validate against envelope contract]
    F --> G[return extracted + meta]
```

**Business context:** live provider behind the same envelope contract as the stub, so the graph is provider-agnostic (BFR-EXT-001). Key read from env only, never stored. Default model `liquid/lfm-2.5-2.6b:free`.
