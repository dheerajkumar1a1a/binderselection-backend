# UI system

One product, two registers: the internal console is a dense precision
instrument; the broker portal is a calm, mobile-first surface. Same tokens,
same components, different density and vocabulary.

## Files

| File | Role |
|---|---|
| `prod/static/app.css` | The only stylesheet. Tokens, shell, components, states, print. |
| `prod/templates/components.html` | Macros: icons, chips, nav, page head, stats, tables, states, dialogs, fields. |
| `prod/templates/base.html` | Shell: rail, page head, toast host, theme resolution, skip link. |
| `prod/static/fonts/`, `prod/static/vendor/` | Inter (variable, latin), Alpine, htmx — vendored, no CDN. |
| `prod/web.py` | Mounts `/static`; registers `money`, `ist`, `dateonly`, `rel` filters. |

## Rules

1. **No colour outside `app.css`.** A template may not contain a hex value.
2. **No `style=` attributes** in page templates. Measured widths (`util`) are the
   one exception, because the value is data, not design.
3. **Compose macros.** A page that hand-rolls a table, chip or button is a bug —
   add the macro instead.
4. **Money is never guessed.** The domain records no currency, so the unit lives
   in the column header and cells stay bare tabular numerals.
5. **Colour encodes meaning, not decoration.** Five tones: `neutral`, `info`,
   `ok`, `warn`, `bad`. Status labels always accompany the colour.
6. **Motion is feedback only.** 120/180/240ms, `cubic-bezier(.2,.8,.2,1)`, and
   everything collapses under `prefers-reduced-motion`.
7. **Destructive actions must survive no-JS.** An append-only action gets a
   server-verifiable confirmation, never a JavaScript-only dialog.

## Tokens

Ink `#111318` / `#e8eaee` · surface `#f6f7f9` / `#0b0d10` · card `#fff` /
`#111418` · accent indigo `#4338ca` / `#8b8cf7` · status ok/warn/bad/info
tuned per theme. Type 11/12/13/14/16/20/28, tabular numerals on every money
cell, mono for identifiers only. Spacing 4/8/12/16/20/24/32/48. Radii 6/10/999.
Two shadow levels.

## Cut status

| Cut | Scope | State |
|---|---|---|
| 0 | tokens, macros, shell, rail, dark mode, vendored assets | **done** |
| 1 | workboard, case | next |
| 2 | rules + capacity consoles | pending |
| 3 | portal, login | pending |
| 4 | audit, accounts, reference, help, doc, error, letter/print | pending |

Known limits carried deliberately: money columns in un-migrated tables are still
left-aligned; workboard tables scroll inside the card until cut 1 wraps them;
`rules_proposal.html`, `reference.html`, `portal*.html`, `admin_users.html` and
`letter.html` are standalone documents and join the shell in their cut.
