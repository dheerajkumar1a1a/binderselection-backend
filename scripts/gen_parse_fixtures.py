"""Generate the parsing dataset (run any time, commit outputs).

python scripts/gen_parse_fixtures.py
Layout: samples/fixtures/<pdf|eml|xlsx|csv|docx|negative>/, >=5 files
per supported type. Negatives prove explicit statuses; oversized inputs
stay synthetic in tests/test_parse.py (never commit 10 MB blobs).
"""
import base64
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "samples" / "fixtures"
for sub in ("pdf", "eml", "xlsx", "csv", "docx", "negative"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


def esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Minimal multi-page PDF with real text (no writer dep)."""
    objs, page_ids, content_ids = [], [], []
    for lines in pages:
        ops = []
        y = 740
        for ln in lines:
            ops.append(f"BT /F1 11 Tf 72 {y} Td ({esc(ln)}) Tj ET")
            y -= 22
        content = "\n".join(ops).encode()
        content_ids.append(len(objs) + 4 + len(page_ids) * 0)
        objs.append(None)  # placeholder, filled below
        page_ids.append((lines, content))
    real, refs, cmap = [], {}, {}
    for i, (lines, content) in enumerate(page_ids):
        ci = len(real) + 4
        refs[i] = ci
        real.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [%s] /Count %d >>"
         % (" ".join(f"{3 + 2 * i} 0 R" for i in range(len(page_ids))), len(page_ids))).encode(),
    ]
    for i in range(len(page_ids)):
        objs.append(
            ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
             f"/Resources << /Font << /F1 {4 + 2 * len(page_ids)} 0 R >> >> "
             f"/Contents {refs[i]} 0 R >>").encode())
        objs.append(real[i])
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # renumber sequentially
    numbered, mapping, out = [], {}, b"%PDF-1.4\n"
    order = [0, 1] + [n for pair in zip(range(2, 2 + 2 * len(page_ids)), []) for n in pair]
    seq = [0, 1]
    for i in range(len(page_ids)):
        seq += [2 + 2 * i, 2 + 2 * i + 1]
    seq.append(2 + 2 * len(page_ids))
    blobs = [objs[0], objs[1]]
    for i in range(len(page_ids)):
        blobs.append(objs[2 + i * 2] if False else None)
    # rebuild cleanly: catalog, pages, then per-page (page, content), then font
    blobs = [objs[0], objs[1]]
    for i in range(len(page_ids)):
        pageno = 3 + 2 * i
        # fix Contents ref inside page dict
        page = objs[2 + 2 * i].replace(f"/Contents {refs[i]} 0 R".encode(),
                                       f"/Contents {pageno + 1} 0 R".encode())
        page = page.replace(f"/F1 {4 + 2 * len(page_ids)} 0 R".encode(),
                            f"/F1 {3 + 2 * len(page_ids)} 0 R".encode())
        blobs += [page, real[i]]
    blobs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    offsets = []
    for i, body in enumerate(blobs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(blobs) + 1}\n0000000000 65535 f \n".encode()
    for o in offsets:
        out += f"{o:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(blobs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF").encode()
    return out


PDF_SET = {
    "demo-upload.pdf": [[
        "MARINE CARGO SUBMISSION - REF DEMO-2026-001",
        "Broker: Acme Marine Ltd",
        "Insured: Harborline Traders, Austin, Texas, US",
        "Total insured value: $6,500,000",
        "Coverage section limit: $2,000,000",
        "Coverage type: ALL_RISK; valuation basis CIF+10%",
        "Requested inception date: 2030-06-01; policy term 12 months",
        "Expiring premium: not disclosed",
        "Warehouse: 12 Port Road, sprinklered, alarm fitted",
        "Commodity: steel machinery parts and watches",
        "Loss history: no claims in the past five years",
    ]],
    "submission.pdf": [[
        "Broker Acme Marine Ltd TIV 6500000 steel",
        "Warehouse 12 Port Road sprinklered",
    ]],
    "loss-run.pdf": [[
        "LOSS RUN - Harborline Traders",
        "2024-03-11 | $6,000 | settled",
        "2023-06-02 | $2,000 | settled",
        "Prior cargo coverage: never cancelled",
    ]],
    "cover-2page.pdf": [
        ["COVER NOTE page 1 - Broker BestCover TIV 8250000",
         "Single warehouse 7 Dockside unsprinklered no alarm"],
        ["COVER NOTE page 2 - Commodity cbd oils",
         "Terms overleaf apply"],
    ],
    "valuation-memo.pdf": [[
        "Valuation memo: basis CIF+10% confirmed",
        "Selling price rejected as non-standard for this facility",
    ]],
}
for name, pages in PDF_SET.items():
    (OUT / "pdf" / name).write_bytes(build_pdf(pages))


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


SOV_CSV = b"Site,Limit,Sprinklered\n12 Port Road,2000000,yes\n44 Quay Street,4500000,yes\n"
(OUT / "eml" / "broker-email.eml").write_bytes(eml(
    "Broker Acme Marine Ltd TIV 6500000 steel. SOV attached.",
    [("sov.csv", SOV_CSV, "text/csv")], subject="Submission S-101"))
inner_csv = b"Site,Limit\nDeep Depot,900000\n"
inner = eml("Forwarded inner submission.", [("data.csv", inner_csv, "text/csv")],
            subject="Fwd: inner submission")
(OUT / "eml" / "nested2.eml").write_bytes(eml(
    "Outer submission with forwarded mail attached.",
    [("inner.eml", inner, "message/rfc822")],
    subject="Outer submission"))
(OUT / "eml" / "plain.eml").write_bytes(
    b"From: broker@acme.example\nTo: uw@example.com\nSubject: TIV query\n"
    b"Content-Type: text/plain; charset=utf-8\n\nJust confirming TIV 6500000 for Harborline.\n")
(OUT / "eml" / "multi-attach.eml").write_bytes(eml(
    "Two attachments: schedule and loss run.",
    [("sov.csv", SOV_CSV, "text/csv"),
     ("losses.csv", b"Date,Amount\n2024-03-11,6000\n", "text/csv")],
    subject="Submission with two attachments"))
(OUT / "eml" / "reminder.eml").write_bytes(eml(
    "Chasing ref DEMO-2026-001. Broker Acme Marine Ltd, nothing new to add.",
    subject="Re: DEMO-2026-001"))

from openpyxl import Workbook


def xlsx(path, sheets):
    wb = Workbook()
    first = True
    for title, rows in sheets:
        ws = wb.active if first else wb.create_sheet(title)
        if first:
            ws.title = title
            first = False
        for r in rows:
            ws.append(r)
    wb.save(path)


xlsx(OUT / "xlsx" / "sov.xlsx", [("SOV", [
    ["Site", "Limit", "Sprinklered"],
    ["12 Port Road", 2000000, "yes"],
    ["44 Quay Street", 4500000, "yes"]])])
xlsx(OUT / "xlsx" / "multi-sheet.xlsx", [
    ("SOV", [["Site", "Limit"], ["12 Port Road", 2000000]]),
    ("LOSSES", [["Date", "Amount"], ["2024-03-11", 6000], ["2023-06-02", 2000]])])
xlsx(OUT / "xlsx" / "schedule-4site.xlsx", [("SOV", [
    ["Site", "Limit", "Sprinklered"],
    ["Alpha Wharf", 1000000, "yes"], ["Beta Dock", 1500000, "yes"],
    ["Gamma Yard", 2000000, "yes"], ["Delta Port", 2500000, "yes"]])])
xlsx(OUT / "xlsx" / "losses-table.xlsx", [("LOSSES", [
    ["Date", "Amount", "Status"],
    ["2024-03-11", 6000, "settled"], ["2023-06-02", 2000, "settled"]])])
xlsx(OUT / "xlsx" / "headers-only.xlsx", [("EMPTY", [["Site", "Limit"]])])

(OUT / "csv" / "sov.csv").write_bytes(SOV_CSV)
(OUT / "csv" / "losses.csv").write_bytes(b"Date,Amount\n2024-03-11,6000\n2023-06-02,2000\n")
(OUT / "csv" / "quoted-commas.csv").write_bytes(
    b'Site,Notes\n"12 Port Road, dock 7","sprinklered, alarmed"\n')
(OUT / "csv" / "latin1.csv").write_bytes(
    "Site,Notes\nDépôt অতিরিক্ত,plain\n".encode("latin-1", "replace"))
(OUT / "csv" / "headers-only.csv").write_bytes(b"Site,Limit\n")

from docx import Document


def docx(path, paras, tables=()):
    doc = Document()
    for p in paras:
        doc.add_paragraph(p)
    for rows in tables:
        t = doc.add_table(rows=len(rows), cols=len(rows[0]))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                t.rows[i].cells[j].text = v
    doc.save(path)


docx(OUT / "docx" / "cover-note.docx",
     ["Broker Acme Marine Ltd TIV 6500000 steel",
      "Warehouse at 12 Port Road is sprinklered."])
docx(OUT / "docx" / "sov-table.docx", ["Schedule of values"],
     [[["Site", "Limit"], ["12 Port Road", "2000000"], ["44 Quay Street", "4500000"]]])
docx(OUT / "docx" / "memo-long.docx",
     [f"Memo paragraph {i}: Harborline Traders renewal terms under review."
      for i in range(1, 11)])
docx(OUT / "docx" / "schedule.docx",
     ["Alpha Wharf sprinklered", "Beta Dock sprinklered",
      "Gamma Yard sprinklered", "Delta Port sprinklered"])
docx(OUT / "docx" / "title-only.docx", ["Harborline submission"])

(OUT / "negative" / "legacy.msg").write_bytes(b"\xd0\xcf\x11\xe0fake-ole-bytes")
(OUT / "negative" / "legacy.xls").write_bytes(b"not-a-real-workbook")
ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)


def _chunk(typ, data):
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


(OUT / "negative" / "scan.png").write_bytes(
    b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
    + _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + _chunk(b"IEND", b""))
img = zlib.compress(b"\x00\xff\x00\x00")
img_obj = (b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
           b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length %d "
           b"/Filter /FlateDecode >>\nstream\n" % len(img) + img + b"\nendstream")
draw = b"q 612 0 0 792 0 0 cm /Im0 Do Q"
sobjs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
    img_obj,
    b"<< /Length %d >>\nstream\n" % len(draw) + draw + b"\nendstream",
]
spdf = b"%PDF-1.4\n"
soff = []
for i, body in enumerate(sobjs, 1):
    soff.append(len(spdf))
    spdf += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
sxref = len(spdf)
spdf += f"xref\n0 {len(sobjs) + 1}\n0000000000 65535 f \n".encode()
for o in soff:
    spdf += f"{o:010d} 00000 n \n".encode()
spdf += (f"trailer\n<< /Size {len(sobjs) + 1} /Root 1 0 R >>\n"
         f"startxref\n{sxref}\n%%EOF").encode()
(OUT / "negative" / "scanned.pdf").write_bytes(spdf)

# keep the published demo PDF identical to the dataset copy
import shutil
shutil.copy(OUT / "pdf" / "demo-upload.pdf",
            Path(__file__).resolve().parent.parent / "docs" / "demo-upload.pdf")

print("wrote:")
for sub in ("pdf", "eml", "xlsx", "csv", "docx", "negative"):
    print(" ", sub, sorted(p.name for p in (OUT / sub).iterdir()))
