# parse.py — document parsing (5 formats)

```mermaid
flowchart TD
    A[uploaded file] --> B{format}
    B -->|pdf| C[pdf text extraction]
    B -->|docx| D[docx text]
    B -->|xlsx| E[xlsx rows]
    B -->|eml/msg| F[email + attachments nesting]
    B -->|txt| G[plain text]
    C --> H[per-document parse status]
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I[limits enforced, explicit failures]
```

**Business context:** real document intake (BFR-EXT); nesting for emails; explicit failures rather than silent skips; limits enforced.

## Example run

Upload "sov.xlsx": format=xlsx → rows parsed into locations/commodities; parse status "ok". Upload "broker.eml" with attachment "sov.pdf": nesting extracts both; status table shows 2 docs. Oversized file → explicit failure, not silent skip.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["upload sov.xlsx + broker.eml"] --> B["xlsx → rows parsed"]
    B --> C["eml → text + nested attachment"]
    C --> D["status table: 2 ok"]
```
