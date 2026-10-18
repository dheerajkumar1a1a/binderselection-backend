# extract_nvidia.py — live LLM extraction (NVIDIA Nemotron)

```mermaid
flowchart TD
    A[documents] --> B[Nemotron-120B request]
    B --> C[with_retry backoff]
    C --> D[parse + validate envelope]
    D --> E[extracted + meta]
```

**Business context:** second live provider, same envelope contract, wired as `llm="nvidia"` (BFR-EXT-001). Used by the nightly extraction eval gate and local UI toggle.

## Example run

Env `NVIDIA_API_KEY` set. Calls Nemotron-120B with same envelope prompt. Used by nightly eval gate (scripts/eval_extraction.py) and local UI toggle. Returns extracted+meta identical in shape to stub/OpenRouter.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["docs text"] --> B["POST NVIDIA Nemotron-120B"]
    B --> C["200 → parse JSON"]
    C --> D["validate envelope → extracted+meta"]
```
