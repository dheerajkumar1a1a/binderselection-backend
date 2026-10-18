# extract.py — document → risk data

```mermaid
flowchart TD
    A[documents] --> B[stub_extract]
    B --> C[for each doc structured_hint]
    C --> D[normalise money]
    D --> E[record value + confidence + source doc id]
    E --> F[track sightings per field]
    F --> G{distinct values > 1?}
    G -->|yes| H[mark contested + store conflict list]
    G -->|no| I[keep first]
    I --> J[ensure mandatory fields present/absent]
    H --> J
```

**Business context:** extraction never silently merges conflicting sources — dual provenance is preserved for the underwriter (BFR-EXT-004/006/007). Missing mandatory fields stay absent (not guessed), so completeness can Refer.
