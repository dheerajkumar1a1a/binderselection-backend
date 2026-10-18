# ui/app.py — local UI

```mermaid
flowchart TD
    A[streamlit app] --> B[upload files]
    B --> C[parse per doc]
    C --> D[extract: stub/openrouter/nvidia]
    D --> E[run graph]
    E --> F[show per-binder outcomes + ranking + narrative]
    F --> G[underwriter action]
    G --> H[settle + audit]
```

**Business context:** local UI over the same graph; supports BYOK OpenRouter/NVIDIA; shows parse status table.

## Example run

User uploads sov.xlsx + broker.eml, picks llm="openrouter" with BYOK key, clicks Run. UI shows parse status table (2 ok), per-binder outcomes (A Accept, B Accept), ranking bar (A 10.0 > B 8.0), narrative, then underwriter accept → settle + audit id.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["upload 2 files"] --> B["parse status ok"]
    B --> C["extract openrouter BYOK"]
    C --> D["A Accept, B Accept, rec A 10.0"]
    D --> E["underwriter accept → audit id"]
```
