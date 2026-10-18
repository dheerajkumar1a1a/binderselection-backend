# extract_nvidia.py — live LLM extraction (NVIDIA Nemotron)

```mermaid
flowchart TD
    A[documents] --> B[Nemotron-120B request]
    B --> C[with_retry backoff]
    C --> D[parse + validate envelope]
    D --> E[extracted + meta]
```

**Business context:** second live provider, same envelope contract, wired as `llm="nvidia"` (BFR-EXT-001). Used by the nightly extraction eval gate and local UI toggle.
