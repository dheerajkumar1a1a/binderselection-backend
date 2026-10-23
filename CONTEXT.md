# Binder Selection Agent — domain glossary

## Outcome vocabulary (engine contract vs display words)

| Engine term (JSON, never changes) | Displayed to humans as | Meaning |
| --- | --- | --- |
| `Pass` | Pass | The rule's condition is satisfied by extracted data. |
| `Decline` | Decline | The rule bites: this risk is outside the binder's stated appetite. Always candidate-excluding. |
| `Cannot assess` | Needs information | The rule's input was absent from the submission, so the rule is held, never silently passed. Display-only mapping in `ui/index.html` and `docs/index.html`. |
| `Refer` (binder-level) | Refer | The binder cannot say yes or no on the provided data; the broker gets a named information-request list. |
| `Excluded` (binder-level) | Excluded | Screened out before appetite rules (capacity full/zero, inactive). |

## Production vocabulary (settled design intent)

| Term | Meaning |
| --- | --- |
| **Case** | The persistent object spanning time: a submission, the evaluations run against it, the recorded decisions, and every successor. The demo's one-shot run becomes a Case with history. |
| **Information request** | A first-class, named list of facts a binder could not assess, issued to the broker. Not free text — each item traces to a rule and a field. |
| **Successor evaluation** | A re-run of the engine on a Case after new information (broker answers, corrections). Linked to its predecessor; the human still decides on the freshest one. |
| **Broker portal** | The broker-facing surface: their own Cases only — ask-lists, document status, and the outcome communicated to them. Brokers never see scores, rules, or other binders' detail. |
| **Reference-data fact** | A third-party fact (wildfire score, flood zone, territory) shown beside extracted values with its source, licence state and timestamp. Provenance follows the same standard as extraction, but the source is a feed rather than a document — and it is still data, never a decision. |
| **Ruleset proposal** | A draft change to a binder's appetite that travels through maker-checker approval and effective-dating before the engine consumes it. |
| **Capacity reservation** | Created by an accepted decision, with a validity window (expiry returns the capacity to free unless the policy incepts); may be released manually. Stale reservations are never allowed to silently eat a binder. |
| **Outcome letter** | The broker-facing communication of a Case's decision — the only view of evaluation results that crosses the broker boundary. |

"These rules are held" in the UI means the per-rule `Cannot assess` rows; it is not a new outcome. The JSON field value emitted by the Python engine and `engine.js` is always `Cannot assess` — every renderer maps it to the display word at paint time.
