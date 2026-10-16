"""Generate binary test fixtures (run once, commit outputs).

python scripts/gen_parse_fixtures.py
Writes samples/fixtures/*.{pdf,xlsx,docx,csv,eml,msg,png}.
PDF is hand-built minimal (no writer dep); xlsx/docx via the new deps;
eml hand-built with a nested csv attachment; msg/png are intentional
negative fixtures (unsupported / ocr_pending).
"""
import base64
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "samples" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

# ---- minimal one-page PDF with real text ----
content = b"BT /F1 12 Tf 72 720 Td (Broker Acme Marine Ltd TIV 6500000 steel) Tj ET"
objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
]
pdf = b"%PDF-1.4\n"
offsets = []
for i, body in enumerate(objs, 1):
    offsets.append(len(pdf))
    pdf += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
xref = len(pdf)
pdf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
for o in offsets:
    pdf += f"{o:010d} 00000 n \n".encode()
pdf += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF").encode()
(OUT / "submission.pdf").write_bytes(pdf)

# ---- xlsx via openpyxl ----
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = "SOV"
ws.append(["Site", "Limit", "Sprinklered"])
ws.append(["12 Port Road", 2000000, "yes"])
ws.append(["44 Quay Street", 4500000, "yes"])
wb.save(OUT / "sov.xlsx")

# ---- docx via python-docx ----
from docx import Document
doc = Document()
doc.add_paragraph("Broker Acme Marine Ltd TIV 6500000 steel")
doc.add_paragraph("Warehouse at 12 Port Road is sprinklered.")
doc.save(OUT / "cover-note.docx")

# ---- csv, eml (with nested csv attachment), negatives ----
(OUT / "sov.csv").write_text(
    "Site,Limit,Sprinklered\n12 Port Road,2000000,yes\n", encoding="utf-8")
nested = base64.b64encode((OUT / "sov.csv").read_bytes()).decode()
(OUT / "broker-email.eml").write_text(
    "From: broker@acme.example\nTo: uw@example.com\n"
    "Subject: Submission S-101\nMIME-Version: 1.0\n"
    'Content-Type: multipart/mixed; boundary="B"\n\n--B\n'
    'Content-Type: text/plain; charset="utf-8"\n\n'
    "Broker Acme Marine Ltd TIV 6500000 steel. SOV attached.\n\n--B\n"
    'Content-Type: text/csv; name="sov.csv"\n'
    "Content-Disposition: attachment; filename=\"sov.csv\"\n"
    "Content-Transfer-Encoding: base64\n\n" + nested + "\n--B--\n",
    encoding="utf-8")
(OUT / "legacy.msg").write_bytes(b"\xd0\xcf\x11\xe0fake-ole-bytes")
(OUT / "legacy.xls").write_bytes(b"not-a-real-workbook")
# ---- nested email: outer -> inner.eml -> data.csv (depth limit demo) ----
inner_csv = b"Site,Limit\nDeep Depot,900000\n"
inner = (
    "From: broker@acme.example\nTo: uw@example.com\n"
    "Subject: Fwd: inner submission\nMIME-Version: 1.0\n"
    'Content-Type: multipart/mixed; boundary="INNER"\n\n--INNER\n'
    'Content-Type: text/plain; charset="utf-8"\n\n'
    "Forwarded inner submission.\n\n--INNER\n"
    'Content-Type: text/csv; name="data.csv"\n'
    'Content-Disposition: attachment; filename="data.csv"\n'
    "Content-Transfer-Encoding: base64\n\n"
    + base64.b64encode(inner_csv).decode() + "\n--INNER--\n"
).encode()
outer = (
    "From: broker@acme.example\nTo: uw@example.com\n"
    "Subject: Outer submission\nMIME-Version: 1.0\n"
    'Content-Type: multipart/mixed; boundary="OUTER"\n\n--OUTER\n'
    'Content-Type: text/plain; charset="utf-8"\n\n'
    "Outer submission with forwarded mail attached.\n\n--OUTER\n"
    'Content-Type: message/rfc822; name="inner.eml"\n'
    'Content-Disposition: attachment; filename="inner.eml"\n'
    "Content-Transfer-Encoding: base64\n\n"
    + base64.b64encode(inner).decode() + "\n--OUTER--\n"
).encode()
(OUT / "nested2.eml").write_bytes(outer)
# ---- scanned PDF: valid file, image XObject, no text layer ----
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
(OUT / "scanned.pdf").write_bytes(spdf)
# 1x1 red PNG (valid file, for ocr_pending path)
def _chunk(typ, data):
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
png = (b"\x89PNG\r\n\x1a\n"
       + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
       + _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
       + _chunk(b"IEND", b""))
(OUT / "scan.png").write_bytes(png)

print("wrote:", sorted(p.name for p in OUT.iterdir()))
