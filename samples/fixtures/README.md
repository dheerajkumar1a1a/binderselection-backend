# Parsing dataset — where the files are, what each proves

All files live in `samples/fixtures/` (repo root sibling: `samples/cases/`
holds the 27 evaluation cases; `fixtures/` holds real byte-level documents).
Regenerate with `python scripts/gen_parse_fixtures.py` (committed outputs are
what tests and demos use).

## Upload these to either UI

- Local UI: `python ui/app.py` → http://127.0.0.1:8099 → file picker
  (posts base64 to `/api/run`, parse-status table in results).
- Public demo: https://dheerajkumar1a1a.github.io/binderselection-backend/
  (in-browser parsing) — or start here with `demo-upload.pdf` via the
  download link on the page.

## The files

| File | Type | Expected status | What it proves |
|---|---|---|---|
| `demo-upload.pdf` | Real 1-page PDF, broker cover note | `parsed` | Full upload demo: with live extraction → A Accept, D+E Decline, B+C Refer |
| `submission.pdf` | Minimal 1-page PDF | `parsed`, pages=1 | PDF text path |
| `scanned.pdf` | Valid PDF, image-only, no text layer | `ocr_pending` | Scan detection (retryable later, never silent) |
| `broker-email.eml` | Multipart email + csv attachment | `parsed` ×2 | 1-level nesting flattens to siblings with `parent_doc_id` |
| `nested2.eml` | Email → attached email → csv | outer/inner `parsed`, csv `failed: max nesting depth` | Recursion stops exactly where BFR-SUB-004 requires |
| `sov.xlsx` | Real spreadsheet (SOV sheet) | `parsed`, sheets=[SOV] | xlsx rows → `Sheet! a \| b` lines |
| `sov.csv` | Delimited SOV | `parsed`, rows counted | csv path incl. encoding fallback |
| `cover-note.docx` | Paragraphs | `parsed` | docx path |
| `legacy.msg` | Fake OLE bytes | `unsupported_format` | Explicit failure naming the format |
| `legacy.xls` | Non-workbook bytes | `unsupported_format` | Legacy Excel deferred, stated not hidden |
| `scan.png` | Valid 1×1 PNG | `ocr_pending` | Image path |

## Not committable (covered in `tests/test_parse.py` instead)

- **Oversized file** (>10 MB → per-doc `failed`, rest proceed) and
  **>10-document submissions** (whole-run halt): generated in-test, never
  committed as 10 MB blobs.
- **Corrupt PDF bytes** and **bad base64**: synthetic byte strings in-test.
- **200 KB single-line csv** proving the 100k-char `text_truncated` flag.
