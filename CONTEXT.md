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
| **Successor evaluation** | A re-run of the engine on the same Case whenever new information arrives (broker answers, corrections). A Case never forks; the human still decides on the freshest one. |
| **Broker portal** | The broker-facing surface: their own Cases only — ask-lists, document status, and the outcome communicated to them. Brokers never see scores, rules, or other binders' detail. |
| **Reference-data fact** | A third-party fact (wildfire score, flood zone, territory) shown beside extracted values with its source, licence state and timestamp. Provenance follows the same standard as extraction, but the source is a feed rather than a document — and it is still data, never a decision. |
| **Ruleset proposal** | A draft change to a binder's appetite that travels through maker-checker approval and effective-dating before the engine consumes it. |
| **Authorised line** | The single authored capacity number per binder — the ceiling against which Written and Reserved are subtracted to produce Available. Versioned and maker-checker approved exactly like a ruleset. Written and Reserved are never authored: they are produced by decisions and reservations. |
| **Capacity proposal** | A draft change to one binder's Authorised line that travels through maker-checker approval and effective-dating before the engine consumes it. The capacity analogue of a Ruleset proposal. |
| **Capacity reservation** | Created by an accepted decision, with a validity window (expiry returns the capacity to free unless the policy incepts); may be released manually. Stale reservations are never allowed to silently eat a binder. Screened against the Authorised line effective on the evaluation date, never against a line landed after that reservation was made. |
| **Request round** | A named batch of information requests issued to the broker at once; one active round per Case. The round is the unit the broker answers and the unit the answer-SLA clock runs on. |
| **Answer** | Broker-supplied data resolving (partly) a Request round - typed portal answers and/or attached documents. An Answer is data from the broker, provenance-marked; it is never a decision. |
| **Outcome letter** | The broker-facing communication of a Case's decision — the only view of evaluation results that crosses the broker boundary. |

## Case status vocabulary (production)

| Status | Meaning |
| --- | --- |
| `new` | Opened, no evaluation yet. Assessment SLA clocks (3 business days). |
| `assessed` | Latest evaluation ran; awaiting the human decision. |
| `awaiting-broker` | A Request round is open — the broker owes answers/documents. The round's answer SLA clock runs (10 business days). |
| `bound` | **Terminal for this release.** Decision recorded + capacity reserved. Corrections still possible via a successor evaluation and a new decision — history is never rewritten. |

"These rules are held" in the UI means the per-rule `Cannot assess` rows; it is not a new outcome. The JSON field value emitted by the Python engine and `engine.js` is always `Cannot assess` — every renderer maps it to the display word at paint time.
