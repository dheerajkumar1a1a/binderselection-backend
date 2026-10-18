# mi.py — MI reports

```mermaid
flowchart TD
    A[load audit records] --> B[volume_mix]
    A --> C[decline_reasons by rule]
    A --> D[override_rate + by reason]
    A --> E[data_quality]
    A --> F[refer_by_field]
    A --> G[stage_timing mean per stage]
    B --> H[report dict]
    C --> H
    D --> H
    E --> H
    F --> H
    G --> H
```

**Business context:** MI-001..006 — volume, decline rank, override rate, quality, refer-by-field, stage timings.

## Example run

report() after one accepted submission: volume_mix {total:1, by_outcome:{Accept:1}, by_broker:{Acme Marine Ltd.:1}}, override_rate {decided:1, overrides:0, rate:0.0}, stage_timing {mean_seconds:{extract:0.01,...}, n:1}.

## Example journey (in-flowchart)

```mermaid
flowchart TD
    A["1 audit record"] --> B["volume_mix: 1 Accept"]
    B --> C["override_rate: 0 overrides"]
    C --> D["stage_timing: extract 0.01s, n=1"]
```
