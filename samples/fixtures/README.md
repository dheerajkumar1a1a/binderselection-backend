# Parsing dataset — where the files are, what each proves

All files live in `samples/fixtures/<type>/` (evaluation cases are the
sibling `samples/cases/`, 27 JSON files). Regenerate everything with
`python scripts/gen_parse_fixtures.py` (committed outputs are what tests
and demos use).

## Upload these to either UI

- Local UI: `python ui/app.py` → http://127.0.0.1:8099 → file picker
  (posts base64 to `/api/run`, parse-status table in results).
- Public demo: https://dheerajkumar1a1a.github.io/binderselection-backend/
  (in-browser parsing) — or start with `docs/demo-upload.pdf` via the
  download link on the page.

## pdf/ (5)

| File | Expected | Proves |
|---|---|---|
| `demo-upload.pdf` | `parsed` | Full upload demo: with live extraction → A Accept, D+E Decline, B+C Refer |
| `submission.pdf` | `parsed` | Minimal PDF text path |
| `loss-run.pdf` | `parsed` | Loss-history content survives parsing |
| `cover-2page.pdf` | `parsed`, pages=2 | Multi-page handling |
| `valuation-memo.pdf` | `parsed` | Code-style tokens (`CIF+10%`) survive byte-for-byte |

## eml/ (5)

| File | Expected | Proves |
|---|---|---|
| `broker-email.eml` | `parsed` ×2 | Attachment flattens to sibling with `parent_doc_id` |
| `nested2.eml` | outer/inner `parsed`, csv `failed: max nesting depth` | Recursion stops exactly where BFR-SUB-004 requires |
| `plain.eml` | `parsed` | Body-only email, no attachments |
| `multi-attach.eml` | `parsed` ×3 | Two attachments, both flattened |
| `reminder.eml` | `parsed` | Short follow-up email |

## xlsx/ (5)

| File | Expected | Proves |
|---|---|---|
| `sov.xlsx` | `parsed`, sheets=[SOV] | Schedule rows → `Sheet! a \| b` lines |
| `multi-sheet.xlsx` | `parsed`, sheets=[SOV, LOSSES] | Multi-sheet iteration |
| `schedule-4site.xlsx` | `parsed` | Four-location schedule |
| `losses-table.xlsx` | `parsed` | Loss table with status column |
| `headers-only.xlsx` | `parsed` | Degenerate headers-only sheet |

## csv/ (5)

| File | Expected | Proves |
|---|---|---|
| `sov.csv` | `parsed` | Baseline delimited schedule |
| `losses.csv` | `parsed` | Loss rows |
| `quoted-commas.csv` | `parsed` | Quoted fields containing commas |
| `latin1.csv` | `parsed` | Non-UTF8 encoding fallback |
| `headers-only.csv` | `parsed` | Headers-only file |

## docx/ (5)

| File | Expected | Proves |
|---|---|---|
| `cover-note.docx` | `parsed` | Paragraph path |
| `sov-table.docx` | `parsed`, tables=1 | Table cells flattened to `a \| b` lines |
| `memo-long.docx` | `parsed`, paragraphs=10 | Multi-paragraph memo |
| `schedule.docx` | `parsed` | Four-site list |
| `title-only.docx` | `parsed` | Degenerate single line |

## negative/ (4 + 1 synthetic)

| File | Expected | Proves |
|---|---|---|
| `legacy.msg` | `unsupported_format` | Explicit failure naming the format |
| `legacy.xls` | `unsupported_format` | Legacy Excel deferred, stated not hidden |
| `scan.png` | `ocr_pending` | Image path, retryable later |
| `scanned.pdf` | `ocr_pending` | Valid PDF with no text layer |
| *(oversized input)* | per-doc `failed` / run halt | Synthetic in `tests/test_parse.py` — never commit 10 MB blobs |

Also synthetic in tests: corrupt PDF bytes, bad base64, 200 KB single-line
csv proving the 100k-char `text_truncated` flag.
