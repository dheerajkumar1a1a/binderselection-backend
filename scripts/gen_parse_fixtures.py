"""Generate the parsing dataset (run any time, commit outputs).

python scripts/gen_parse_fixtures.py
Layout: samples/fixtures/<pdf|eml|xlsx|csv|docx|negative>/, >=5 files
per supported type. Negatives prove explicit statuses; oversized inputs
stay synthetic in tests/test_parse.py (never commit 10 MB blobs).
"""
# base64: encode attachments.
import base64
# struct: PNG chunk packing.
import struct
# zlib: compression.
import zlib
# Path: filesystem.
from pathlib import Path

# OUT: output dir.
OUT = Path(__file__).resolve().parent.parent / "samples" / "fixtures"
# Create subdirs.
for sub in ("pdf", "eml", "xlsx", "csv", "docx", "negative"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


# esc: escape special chars for PDF text.
def esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# build_pdf: minimal multi-page PDF with real text.
def build_pdf(pages: list[list[str]]) -> bytes:
    objs, page_ids, content_ids = [], [], []
    for lines in pages:
        ops = []
        y = 740
        for ln in lines:
            ops.append(f"BT /F1 11 Tf 72 {y} Td ({esc(ln)}) Tj ET")
            y -= 22
        content = "\n".join(ops).encode()
        content_ids.append(len(objs) + 4 + len(page_ids) * 0)
        objs.append(None)
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
    blobs = [objs[0], objs[1]]
    for i in range(len(page_ids)):
        pageno = 3 + 2 * i
        page = objs[2 + 2 * i].replace(f"/Contents {refs[i]} 0 R".encode(),
                                       f"/Contents {pageno + 1} 0 R".encode())
        page = page.replace(f"/F1 {4 + 2 * len(page_ids)} 0 R".encode(),
                            f"/F1 {3 + 2 * len(page_ids)} 0 R".encode())
        blobs += [page, real[i]]
    blobs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    offsets = []
    out = b"%PDF-1.4\n"
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


# PDF_SET: named PDF fixtures.
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
        "MARINE CARGO SUBMISSION - REF SUB-2024-1187",
        "From: Acme Marine Ltd, 4 Lime Street, London EC3M 7AA",
        "To: Binder Underwriting Team",
        "Date: 12 March 2024",
        "Insured: Harborline Traders Ltd, Austin, Texas, US",
        "Business: general warehousing and distribution, trading since 2009",
        "Broker Acme Marine Ltd TIV 6500000 steel",
        "Total insured value $6,500,000 across 3 scheduled locations",
        "Warehouse 12 Port Road sprinklered",
        "Site 2: 44 Quay Street, sprinklered, built 2001, alarm fitted",
        "Site 3: 7 Dockside, sprinklered, built 1998, alarm fitted",
        "Commodity: steel machinery parts, packed in cases",
        "Coverage requested: All Risk including warehouse storage and transit",
        "Valuation basis CIF+10%, policy term 12 months from 1 June 2024",
        "Loss history: one settled claim $4,000 in March 2021, none since",
        "Expiring premium not disclosed. Profit share not requested.",
        "Contact: J. Whitaker, j.whitaker@acme.example, +44 20 7946 0018",
    ]],
    "loss-run.pdf": [[
        "LOSS RUN - Harborline Traders",
        "Issued by: Meridian Claims Services, ref LR-2024-0091",
        "Policy period under review: 2019-2024",
        "2024-03-11 | $6,000 | water damage, Hull depot | settled",
        "2023-06-02 | $2,000 | forklift impact, Quay Street | settled",
        "2021-09-14 | $4,000 | storm ingress, Dockside | settled",
        "2020-01-22 | $1,500 | handling damage, Port Road | settled",
        "Total incurred: $13,500 across 4 claims",
        "Largest single claim: $6,000",
        "Prior cargo coverage: never cancelled",
        "Prior coverage never non-renewed by any carrier",
        "Contact: claims@meridian.example",
    ]],
    "cover-2page.pdf": [
        ["COVER NOTE page 1 - Broker BestCover TIV 8250000",
         "Insured: Seabright Foods plc, Felixstowe, UK",
         "Single warehouse 7 Dockside unsprinklered no alarm",
         "Commodity: frozen fish and seafood, reefer transit",
         "Coverage section limit $2,500,000 per section",
         "Requested inception: 1 September 2024, term 12 months",
         "See page 2 for conditions and warranties"],
        ["COVER NOTE page 2 - conditions and warranties",
         "Warranted: temperature logs maintained throughout transit",
         "Warranted: no single shipment to exceed $500,000",
         "Survey clause: pre-shipment survey for consignments over $250,000",
         "Expiring premium disclosed: $41,000",
         "Terms overleaf apply"],
    ],
    "valuation-memo.pdf": [[
        "VALUATION MEMO - private and confidential",
        "To: Binder facility B underwriters",
        "From: Acme Marine Ltd, valuation desk",
        "Date: 28 May 2024",
        "Re: Harborline Traders renewal",
        "Valuation memo: basis CIF+10% confirmed",
        "Selling price rejected as non-standard for this facility",
        "CIF value evidenced by supplier invoices totalling $5,900,000",
        "Plus 10% uplift applied per facility wording",
        "Currencies normalised to USD at submission date rates",
    ]],
}
# Write PDFs.
for name, pages in PDF_SET.items():
    (OUT / "pdf" / name).write_bytes(build_pdf(pages))

# SOV CSV shared across eml/xlsx.
SOV_CSV = ("Site,Limit,Sprinklered,Alarm,YearBuilt\n"
           "12 Port Road,2000000,yes,hardwired,2001\n"
           "44 Quay Street,4500000,yes,hardwired,2001\n"
           "7 Dockside,1200000,yes,local,1998\n"
           "9 Pier End,800000,yes,hardwired,2005\n"
           "Alpha Wharf,1000000,yes,hardwired,2010\n"
           "Beta Dock,1500000,yes,local,2007\n"
           "Gamma Yard,2000000,yes,hardwired,2015\n"
           "Delta Port,2500000,yes,hardwired,2018\n").encode()
# broker email.
(OUT / "eml" / "broker-email.eml").write_bytes(eml(
    "Dear Underwriter,\n\nPlease quote our client Harborline Traders Ltd "
    "(ref SUB-2024-1187) for marine cargo and stock throughput.\n\n"
    "Headlines: TIV $6,500,000 across 8 scheduled warehouses; commodity is "
    "steel machinery parts in cases; all sites sprinklered; loss history is "
    "one settled $4,000 claim in 2021 and nothing since.\n\n"
    "Full schedule of values is attached as sov.csv (8 sites with limits, "
    "alarm types and build years). Cover sought is All Risk including "
    "warehouse storage and transit, valuation CIF+10%, 12 months from "
    "1 June 2024. Expiring premium not disclosed; profit share not requested.\n\n"
    "Grateful for terms by Friday.\n\nKind regards,\nJ. Whitaker\n"
    "Acme Marine Ltd | j.whitaker@acme.example | +44 20 7946 0018",
    [("sov.csv", SOV_CSV, "text/csv")], subject="Submission S-101"))
# nested email with inner rfc822.
inner_csv = b"Site,Limit\nDeep Depot,900000\n"
inner = eml("Forwarded inner submission.", [("data.csv", inner_csv, "text/csv")],
            subject="Fwd: inner submission")
(OUT / "eml" / "nested2.eml").write_bytes(eml(
    "Outer submission with forwarded mail attached.",
    [("inner.eml", inner, "message/rfc822")],
    subject="Outer submission"))
# plain text email.
(OUT / "eml" / "plain.eml").write_bytes(
    b"From: broker@acme.example\nTo: uw@example.com\nSubject: TIV query\n"
    b"Content-Type: text/plain; charset=utf-8\n\nHi,\n\nJust confirming TIV 6500000 for Harborline "
    b"ahead of tomorrow's bordereau. Full pack to follow.\n\nThanks,\nJ.\n")
# multi-attach email.
(OUT / "eml" / "multi-attach.eml").write_bytes(eml(
    "As discussed, please find two attachments: the schedule of values "
    "and the five-year loss run for Harborline Traders (4 settled claims, "
    "largest $6,000, prior cargo cover never cancelled).",
    [("sov.csv", SOV_CSV, "text/csv"),
     ("losses.csv", b"Date,Amount,Status\n2024-03-11,6000,settled\n2023-06-02,2000,settled\n"
                    b"2021-09-14,4000,settled\n2020-01-22,1500,settled\n", "text/csv")],
    subject="Submission with two attachments"))
# reminder email.
(OUT / "eml" / "reminder.eml").write_bytes(eml(
    "Chasing ref DEMO-2026-001, submitted last Tuesday via this address. "
    "Broker Acme Marine Ltd, nothing new to add except the surveyor has "
    "now confirmed the sprinkler service date. Please confirm safe receipt.",
    subject="Re: DEMO-2026-001"))

# xlsx generation.
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


SITES_8 = [["Site", "Limit", "Sprinklered", "Alarm", "YearBuilt"],
           ["12 Port Road", 2000000, "yes", "hardwired", 2001],
           ["44 Quay Street", 4500000, "yes", "hardwired", 2001],
           ["7 Dockside", 1200000, "yes", "local", 1998],
           ["9 Pier End", 800000, "yes", "hardwired", 2005],
           ["Alpha Wharf", 1000000, "yes", "hardwired", 2010],
           ["Beta Dock", 1500000, "yes", "local", 2007],
           ["Gamma Yard", 2000000, "yes", "hardwired", 2015],
           ["Delta Port", 2500000, "yes", "hardwired", 2018]]
LOSSES_5 = [["Date", "Amount", "Status", "Cause"],
            ["2024-03-11", 6000, "settled", "water damage, Hull depot"],
            ["2023-06-02", 2000, "settled", "forklift impact, Quay Street"],
            ["2021-09-14", 4000, "settled", "storm ingress, Dockside"],
            ["2020-01-22", 1500, "settled", "handling damage, Port Road"],
            ["2019-05-30", 900, "settled", "pilferage, Beta Dock"]]
xlsx(OUT / "xlsx" / "sov.xlsx", [("SOV", SITES_8)])
xlsx(OUT / "xlsx" / "multi-sheet.xlsx", [
    ("SOV", [r[:3] for r in SITES_8]),
    ("LOSSES", [r[:3] for r in LOSSES_5])])
xlsx(OUT / "xlsx" / "schedule-4site.xlsx", [("SOV", [
    ["Site", "Limit", "Sprinklered", "Alarm", "YearBuilt"],
    ["Alpha Wharf", 1000000, "yes", "hardwired", 2010],
    ["Beta Dock", 1500000, "yes", "local", 2007],
    ["Gamma Yard", 2000000, "yes", "hardwired", 2015],
    ["Delta Port", 2500000, "yes", "hardwired", 2018]])])
xlsx(OUT / "xlsx" / "losses-table.xlsx", [("LOSSES", LOSSES_5)])
xlsx(OUT / "xlsx" / "headers-only.xlsx", [("EMPTY", [["Site", "Limit"]])])

# CSV files.
(OUT / "csv" / "sov.csv").write_bytes(
    _csv_block("Site,Limit,Sprinklered,Alarm,YearBuilt", SITES_8[1:]))
(OUT / "csv" / "losses.csv").write_bytes(
    _csv_block("Date,Amount,Status", [r[:3] for r in LOSSES_5[1:]]))
(OUT / "csv" / "quoted-commas.csv").write_bytes(
    b'Site,Notes,Contact\n"12 Port Road, dock 7","sprinklered, alarmed","J. Whitaker, Acme"\n'
    b'"44 Quay Street, berth 2","sprinklered, hardwired alarm","A. Shah, Acme"\n')
(OUT / "csv" / "latin1.csv").write_bytes(
    ("Site,Notes\nDAcpA't ��.���ݨ����ݨ���?��,plain\nCafAc Quay,rAcservAc\n").encode("latin-1", "replace"))
(OUT / "csv" / "headers-only.csv").write_bytes(b"Site,Limit\n")

# DOCX files.
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
     ["COVER NOTE - Harborline Traders Ltd renewal",
      "Broker Acme Marine Ltd TIV 6500000 steel",
      "Insured trades as a general warehousing and distribution group from "
      "three scheduled sites, all sprinklered with maintained alarm systems.",
      "Warehouse at 12 Port Road is sprinklered. Two further sites at "
      "44 Quay Street and 7 Dockside carry limits of $4,500,000 and $1,200,000.",
      "Commodity is steel machinery parts packed in export cases.",
      "Cover sought is All Risk including storage and transit, valuation "
      "CIF+10%, twelve months. Expiring premium not disclosed."])
docx(OUT / "docx" / "sov-table.docx", ["Schedule of values - all limits USD"],
     [[["Site", "Limit", "Sprinklered", "Alarm"],
       ["12 Port Road", "2000000", "yes", "hardwired"],
       ["44 Quay Street", "4500000", "yes", "hardwired"],
       ["7 Dockside", "1200000", "yes", "local"]]])
docx(OUT / "docx" / "memo-long.docx",
     [f"Memo paragraph {i}: Harborline Traders renewal terms under review. "
      f"Underwriter notes from meeting {i} cover capacity, wording and "
      f"survey requirements for the coming policy year."
      for i in range(1, 11)])
docx(OUT / "docx" / "schedule.docx",
     ["SCHEDULE OF LOCATIONS",
      "Alpha Wharf - sprinklered, hardwired alarm, built 2010",
      "Beta Dock - sprinklered, local alarm, built 2007",
      "Gamma Yard - sprinklered, hardwired alarm, built 2015",
      "Delta Port - sprinklered, hardwired alarm, built 2018"])
docx(OUT / "docx" / "title-only.docx", ["Harborline submission"])

# Negatives.
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

# Keep demo PDF identical to dataset copy.
import shutil
shutil.copy(OUT / "pdf" / "demo-upload.pdf",
            Path(__file__).resolve().parent.parent / "docs" / "demo-upload.pdf")

print("wrote:")
for sub in ("pdf", "eml", "xlsx", "csv", "docx", "negative"):
    print(" ", sub, sorted(p.name for p in (OUT / sub).iterdir()))
