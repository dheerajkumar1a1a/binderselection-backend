"""Generate per-case parsing fixtures: one file per sample case per type.

Layout: samples/fixtures/<pdf|eml|xlsx|csv|docx>/case-NN-<case_id>.<ext>
One document set per the 27 sample cases, so every case has a representative
in every supported format. Negatives remain in samples/fixtures/negative/.
"""
# base64: encode attachments.
import base64
# json: read cases/manifest.
import json
# struct: PNG chunk packing (unused here but kept).
import struct
# zlib: PNG compression (unused here but kept).
import zlib
# Path: filesystem paths.
from pathlib import Path

# ROOT: repo root.
ROOT = Path(__file__).resolve().parent.parent
# OUT: output fixtures dir.
OUT = ROOT / "samples" / "fixtures"
# CASES_DIR: sample cases dir.
CASES_DIR = ROOT / "samples" / "cases"
# MANIFEST: loaded manifest.
MANIFEST = json.loads((ROOT / "samples" / "manifest.json").read_text(encoding="utf-8"))

# Create output subdirs.
for sub in ("pdf", "eml", "xlsx", "csv", "docx"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


# esc: escape special chars for PDF text.
def esc(s):
    return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# build_pdf: minimal multi-page PDF with real text.
def build_pdf(pages):
    real = []
    for lines in pages:
        ops = []
        y = 740
        for ln in lines:
            ops.append(f"BT /F1 11 Tf 72 {y} Td ({esc(ln)}) Tj ET")
            y -= 22
        content = "\n".join(ops).encode()
        real.append((lines, content))
    blobs = [b"<< /Type /Catalog /Pages 2 0 R >>",
             ("<< /Type /Pages /Kids [%s] /Count %d >>"
              % (" ".join(f"{3 + 2 * i} 0 R" for i in range(len(real))), len(real))).encode()]
    for i, (lines, content) in enumerate(real):
        page = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {3 + 2 * len(real)} 0 R >> >> "
                f"/Contents {4 + 2 * i} 0 R >>").encode()
        blobs.append(page)
        blobs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    blobs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for body in blobs:
        offsets.append(len(out))
        out += f"{len(offsets)} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(blobs) + 1}\n0000000000 65535 f \n".encode()
    for o in offsets:
        out += f"{o:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(blobs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF").encode()
    return out


# eml: build a multipart email with attachments.
def eml(body_text, attachments=(), subject="Submission"):
    parts = ["From: broker@acme.example\nTo: uw@example.com\n"
             f"Subject: {subject}\nMIME-Version: 1.0\n"
             'Content-Type: multipart/mixed; boundary="B"\n\n--B\n'
             'Content-Type: text/plain; charset="utf-8"\n\n' + body_text + "\n"]
    for fname, data, ctype in attachments:
        parts.append("--B\nContent-Type: %s; name=\"%s\"\n"
                     "Content-Disposition: attachment; filename=\"%s\"\n"
                     "Content-Transfer-Encoding: base64\n\n%s\n"
                     % (ctype, fname, fname, base64.b64encode(data).decode()))
    return ("\n".join(parts) + "--B--\n").encode()


# _csv_block: build CSV bytes from header + rows.
def _csv_block(header, rows):
    lines = [header]
    for r in rows:
        lines.append(",".join(str(c) for c in r))
    return ("\n".join(lines) + "\n").encode()


# case_summary: extract tiv/broker/locations/commodities from a case.
def case_summary(case):
    docs = case.get("documents", [])
    hints = []
    for d in docs:
        h = d.get("structured_hint", {}) or {}
        hints.append(h)
    tiv = None
    broker = None
    locs = []
    comms = []
    for h in hints:
        if tiv is None and "total_insured_value" in h:
            tiv = h["total_insured_value"]
        if broker is None and "broker_name" in h:
            broker = h["broker_name"]
        locs += h.get("locations", []) or []
        comms += h.get("commodities", []) or []
    if tiv is None:
        tiv = "not stated"
    if broker is None:
        broker = "not stated"
    return tiv, broker, locs, comms


# main: generate per-case fixtures for all 5 types.
def main():
    for c in MANIFEST["cases"]:
        cid = c["id"]
        case = json.loads((CASES_DIR / c["file"]).read_text(encoding="utf-8"))
        tiv, broker, locs, comms = case_summary(case)
        n = int(c["file"].split("-")[0])
        tag = f"case-{n:02d}-{cid}"
        comm_str = ", ".join(x.get("commodity_type", str(x)) for x in comms) or "not stated"
        loc_lines = [f"{l.get('address','?')} (sprinklered={l.get('sprinklered')})" for l in locs] or ["(none stated)"]

        # PDF
        pages = [[
            f"MARINE CARGO SUBMISSION - {case.get('case_id', cid).upper()}",
            f"Broker: {broker}",
            f"Total insured value: {tiv}",
            f"Commodity: {comm_str}",
            "Locations:",
        ] + [f"  - {l}" for l in loc_lines] + [
            f"Expected: {case.get('expected', {}).get('recommendation', '?')}",
            f"Covers: {', '.join(case.get('covers', []))}",
        ]]
        (OUT / "pdf" / f"{tag}.pdf").write_bytes(build_pdf(pages))

        # CSV sov
        rows = [["Site", "Sprinklered"]]
        for l in locs:
            rows.append([l.get("address", "?"), "yes" if l.get("sprinklered") else "no"])
        if len(rows) == 1:
            rows.append(["(none)", ""])
        (OUT / "csv" / f"{tag}.csv").write_bytes(_csv_block("Site,Sprinklered", rows[1:]))

        # XLSX
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "SOV"
            for r in rows:
                ws.append(r)
            wb.save(OUT / "xlsx" / f"{tag}.xlsx")
        except Exception:
            pass

        # EML
        body = (f"Dear Underwriter,\n\nPlease quote {broker} (ref {case.get('case_id', cid)}) "
                f"for marine cargo. TIV {tiv}. Commodity: {comm_str}. "
                f"Locations: {', '.join(l.get('address','?') for l in locs) or 'see SOV'}.\n\n"
                f"Expected outcome: {case.get('expected', {}).get('recommendation', '?')}.\n\n"
                f"Regards,\nBroker\n")
        sov_csv = _csv_block("Site,Sprinklered", rows[1:])
        (OUT / "eml" / f"{tag}.eml").write_bytes(
            eml(body, [("sov.csv", sov_csv, "text/csv")], subject=f"Submission {cid}"))

        # DOCX
        try:
            from docx import Document
            doc = Document()
            doc.add_paragraph(f"COVER NOTE - {case.get('case_id', cid)}")
            doc.add_paragraph(f"Broker: {broker}")
            doc.add_paragraph(f"Total insured value: {tiv}")
            doc.add_paragraph(f"Commodity: {comm_str}")
            for l in loc_lines:
                doc.add_paragraph(l)
            doc.add_paragraph(f"Expected: {case.get('expected', {}).get('recommendation', '?')}")
            doc.save(OUT / "docx" / f"{tag}.docx")
        except Exception:
            pass

    print(f"generated {len(MANIFEST['cases'])} cases x 5 types")


if __name__ == "__main__":
    main()
