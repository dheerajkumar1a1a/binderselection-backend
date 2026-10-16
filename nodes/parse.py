"""Document parsing: file bytes -> text, one status per document.

Covers BFR-SUB-002 (pdf, eml, xlsx, csv, docx), SUB-004 (email attachments
recurse one level into flat siblings), SUB-005 (explicit per-document
failure, never silently discarded), SUB-006 (10 docs / 10 MB limits),
SUB-008 (image/scanned input -> ocr_pending, retryable later).

Boundary (locked): parse outputs *text*, extract outputs *fields*.
Byte payloads are dropped after parsing; raw retention is the document
store's job (DEP-3), not graph state. Documents arriving with text and no
bytes (tests, hints, LLM-prefilled) pass through as `pre-parsed`.
"""
import base64
import csv
import io
from email import policy
from email.parser import BytesParser

MAX_DOCS = 10
MAX_BYTES = 10_000_000
MAX_TEXT_CHARS = 100_000
MAX_NESTING = 1

STATUS_PARSED = "parsed"
STATUS_PREPARSED = "pre-parsed"
STATUS_UNSUPPORTED = "unsupported_format"
STATUS_OCR_PENDING = "ocr_pending"
STATUS_FAILED = "failed"


def _ext(filename: str) -> str:
    name = (filename or "").lower()
    return name.rsplit(".", 1)[-1] if "." in name else ""


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS], True
    return text, False


def _parse_pdf(data: bytes) -> tuple[str, dict]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n".join(pages)
    meta = {"pages": len(reader.pages)}
    if not text.strip():
        return "", meta, STATUS_OCR_PENDING, "no text layer (scanned?)"
    return text, meta, STATUS_PARSED, ""


def _parse_eml(data: bytes) -> tuple[str, dict, list]:
    msg = BytesParser(policy=policy.default).parsebytes(data)
    chunks, attachments = [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = (part.get_content_disposition() or "")
        payload = part.get_payload(decode=True) or b""
        if disp == "attachment" or (disp != "inline" and part.get_filename()):
            attachments.append({
                "filename": part.get_filename() or "attachment.bin",
                "content_bytes": payload,
            })
        elif part.get_content_type() == "text/plain":
            try:
                chunks.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
            except Exception:
                chunks.append("")
    return "\n".join(chunks), {"subject": str(msg.get("subject", ""))}, attachments


def _parse_xlsx(data: bytes) -> tuple[str, dict]:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines, sheets = [], []
    for ws in wb.worksheets:
        sheets.append(ws.title)
        for row in ws.iter_rows(values_only=True):
            vals = [str(c) for c in row if c is not None]
            if vals:
                lines.append(f"{ws.title}! " + " | ".join(vals))
    return "\n".join(lines), {"sheets": sheets}, STATUS_PARSED, ""


def _parse_csv(data: bytes) -> tuple[str, dict]:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        return "", {}, STATUS_FAILED, "undecodable bytes"
    rows = list(csv.reader(io.StringIO(text)))
    return "\n".join(" | ".join(r) for r in rows), {"rows": len(rows)}, STATUS_PARSED, ""


def _parse_docx(data: bytes) -> tuple[str, dict]:
    from docx import Document
    doc = Document(io.BytesIO(data))
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    tables = sum(1 for _ in doc.tables)
    for table in doc.tables:
        for row in table.rows:
            vals = [c.text.strip() for c in row.cells if c.text.strip()]
            if vals:
                paras.append(" | ".join(vals))
    return "\n".join(paras), {"paragraphs": len(paras), "tables": tables}, STATUS_PARSED, ""


def parse_one(doc: dict, depth: int = 0) -> tuple[dict, list]:
    """Parse a single document. Returns (enriched doc, child docs)."""
    out = {k: v for k, v in doc.items() if k not in ("content_bytes", "content_b64")}
    raw = doc.get("content_bytes")
    if raw is None and doc.get("content_b64"):
        try:
            raw = base64.b64decode(doc["content_b64"])
        except Exception:
            out.update(parse_status=STATUS_FAILED, failure_reason="invalid base64")
            return out, []
    if raw is None:
        out.setdefault("parse_status", STATUS_PREPARSED)
        return out, []
    out["size_bytes"] = len(raw)
    if len(raw) > MAX_BYTES:
        out.update(parse_status=STATUS_FAILED, failure_reason=f"size {len(raw)} exceeds {MAX_BYTES} limit")
        return out, []
    ext = _ext(doc.get("filename"))
    try:
        if ext == "pdf":
            text, meta, status, reason = _parse_pdf(raw)
            children = []
        elif ext == "eml":
            if depth >= MAX_NESTING:
                out.update(parse_status=STATUS_FAILED, failure_reason="max nesting depth")
                return out, []
            text, meta, attachments = _parse_eml(raw)
            children = []
            for i, att in enumerate(attachments):
                child, _ = parse_one({
                    "doc_id": f"{doc.get('doc_id', 'doc')}-att{i}",
                    "filename": att["filename"],
                    "content_bytes": att["content_bytes"],
                    "parent_doc_id": doc.get("doc_id"),
                }, depth + 1)
                children.append(child)
            status, reason = STATUS_PARSED, ""
        elif ext == "xlsx":
            text, meta, status, reason = _parse_xlsx(raw)
            children = []
        elif ext == "csv":
            text, meta, status, reason = _parse_csv(raw)
            children = []
        elif ext == "docx":
            text, meta, status, reason = _parse_docx(raw)
            children = []
        elif ext in ("png", "jpg", "jpeg", "tiff", "bmp", "gif"):
            out.update(parse_status=STATUS_OCR_PENDING, failure_reason="image input, OCR engine pending",
                       format=ext)
            return out, []
        else:
            out.update(parse_status=STATUS_UNSUPPORTED,
                       failure_reason=f"format '.{ext or '?'}' has no parser", format=ext)
            return out, []
    except Exception as e:
        out.update(parse_status=STATUS_FAILED,
                   failure_reason=f"{type(e).__name__}: {e}", format=ext)
        return out, []
    text, truncated = _truncate(text)
    out.update(format=ext, text=text, text_truncated=truncated,
               parse_status=status, failure_reason=reason, **meta)
    return out, children


def parse_documents(documents: list[dict]) -> dict:
    """Graph-node-shaped: enrich every document, never drop one."""
    docs = documents or []
    if len(docs) > MAX_DOCS:
        return {"documents": docs,
                "parse": {"halted": True,
                          "reason": f"{len(docs)} documents exceeds {MAX_DOCS} limit"}}
    enriched = []
    for doc in docs:
        parsed, children = parse_one(doc)
        enriched.append(parsed)
        enriched.extend(children)
    failures = [{"doc_id": d.get("doc_id"), "status": d.get("parse_status"),
                 "reason": d.get("failure_reason", "")}
                for d in enriched if d.get("parse_status") not in (STATUS_PARSED, STATUS_PREPARSED)]
    return {"documents": enriched,
            "parse": {"halted": False, "failures": failures}}
