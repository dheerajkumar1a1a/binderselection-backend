# Binder Selection Agent — domain glossary

## Outcome vocabulary (engine contract vs display words)

| Engine term (JSON, never changes) | Displayed to humans as | Meaning |
| --- | --- | --- |
| `Pass` | Pass | The rule's condition is satisfied by extracted data. |
| `Decline` | Decline | The rule bites: this risk is outside the binder's stated appetite. Always candidate-excluding. |
| `Cannot assess` | Needs information | The rule's input was absent from the submission, so the rule is held, never silently passed. Display-only mapping in `ui/index.html` and `docs/index.html`. |
| `Refer` (binder-level) | Refer | The binder cannot say yes or no on the provided data; the broker gets a named information-request list. |
| `Excluded` (binder-level) | Excluded | Screened out before appetite rules (capacity full/zero, inactive). |

"These rules are held" in the UI means the per-rule `Cannot assess` rows; it is not a new outcome. The JSON field value emitted by the Python engine and `engine.js` is always `Cannot assess` — every renderer maps it to the display word at paint time.
