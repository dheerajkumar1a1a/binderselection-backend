"""Document parsing dataset: every fixture parses to its designed status.

Layout: samples/fixtures/<pdf|eml|xlsx|csv|docx|negative>/, >=5 files
per supported type (see samples/fixtures/README.md). Oversized inputs
stay synthetic (never commit 10 MB blobs).
"""
import base64
from pathlib import Path
import pytest
from nodes import parse as P

FIX = Path(__file__).resolve().parent.parent / "samples" / "fixtures"


def _doc(sub: str, name: str, doc_id: str = "d1") -> dict:
    return {"doc_id": doc_id, "filename": name,
            "content_bytes": (FIX / sub / name).read_bytes()}


def _status(sub: str, name: str) -> str:
    out, _ = P.parse_one(_doc(sub, name))
    return out["parse_status"]


@pytest.mark.parametrize("name", ["demo-upload.pdf", "submission.pdf",
                                  "loss-run.pdf", "cover-2page.pdf",
                                  "valuation-memo.pdf"])
def test_pdf_folder_all_parse(name):
    assert _status("pdf", name) == "parsed"


@pytest.mark.parametrize("name", ["broker-email.eml", "nested2.eml",
                                  "plain.eml", "multi-attach.eml",
                                  "reminder.eml"])
def test_eml_folder_all_parse(name):
    assert _status("eml", name) == "parsed"


@pytest.mark.parametrize("name", ["sov.xlsx", "multi-sheet.xlsx",
                                  "schedule-4site.xlsx", "losses-table.xlsx",
                                  "headers-only.xlsx"])
def test_xlsx_folder_all_parse(name):
    assert _status("xlsx", name) == "parsed"


@pytest.mark.parametrize("name", ["sov.csv", "losses.csv", "quoted-commas.csv",
                                  "latin1.csv", "headers-only.csv"])
def test_csv_folder_all_parse(name):
    assert _status("csv", name) == "parsed"


@pytest.mark.parametrize("name", ["cover-note.docx", "sov-table.docx",
                                  "memo-long.docx", "schedule.docx",
                                  "title-only.docx"])
def test_docx_folder_all_parse(name):
    assert _status("docx", name) == "parsed"


@pytest.mark.parametrize("name, want", [("legacy.msg", "unsupported_format"),
                                        ("legacy.xls", "unsupported_format"),
                                        ("scan.png", "ocr_pending"),
                                        ("scanned.pdf", "ocr_pending")])
def test_negative_folder_statuses(name, want):
    assert _status("negative", name) == want


def test_pdf_content_spot_checks():
    out, _ = P.parse_one(_doc("pdf", "loss-run.pdf"))
    assert "$6,000" in out["text"] and "never cancelled" in out["text"]
    two, _ = P.parse_one(_doc("pdf", "cover-2page.pdf"))
    assert two["pages"] == 2 and "page 2" in two["text"]
    memo, _ = P.parse_one(_doc("pdf", "valuation-memo.pdf"))
    assert "CIF+10%" in memo["text"]
    demo, _ = P.parse_one(_doc("pdf", "demo-upload.pdf"))
    assert "DEMO-2026-001" in demo["text"]


def test_eml_content_spot_checks():
    res = P.parse_documents([_doc("eml", "multi-attach.eml", "m")])
    assert [d["doc_id"] for d in res["documents"]] == ["m", "m-att0", "m-att1"]
    assert all(d["parse_status"] == "parsed" for d in res["documents"])
    plain, _ = P.parse_one(_doc("eml", "plain.eml"))
    assert "TIV 6500000" in plain["text"]
    rem, _ = P.parse_one(_doc("eml", "reminder.eml"))
    assert "DEMO-2026-001" in rem["text"]


def test_xlsx_content_spot_checks():
    multi, _ = P.parse_one(_doc("xlsx", "multi-sheet.xlsx"))
    assert multi["sheets"] == ["SOV", "LOSSES"] and "6000" in multi["text"]
    sched, _ = P.parse_one(_doc("xlsx", "schedule-4site.xlsx"))
    assert "Delta Port" in sched["text"]
    empty, _ = P.parse_one(_doc("xlsx", "headers-only.xlsx"))
    assert empty["parse_status"] == "parsed" and "Site" in empty["text"]


def test_csv_content_spot_checks():
    quoted, _ = P.parse_one(_doc("csv", "quoted-commas.csv"))
    assert "dock 7" in quoted["text"]
    latin, _ = P.parse_one(_doc("csv", "latin1.csv"))
    assert latin["parse_status"] == "parsed"
    losses, _ = P.parse_one(_doc("csv", "losses.csv"))
    assert "6000" in losses["text"]


def test_docx_content_spot_checks():
    table, _ = P.parse_one(_doc("docx", "sov-table.docx"))
    assert table["tables"] == 1 and "4500000" in table["text"]
    memo, _ = P.parse_one(_doc("docx", "memo-long.docx"))
    assert memo["paragraphs"] == 10
    sched, _ = P.parse_one(_doc("docx", "schedule.docx"))
    assert "Delta Port" in sched["text"]


def test_pdf_reports_pages_xlsx_reports_sheets():
    pdf, _ = P.parse_one(_doc("pdf", "demo-upload.pdf"))
    assert pdf["pages"] == 1
    xlsx, _ = P.parse_one(_doc("xlsx", "sov.xlsx"))
    assert xlsx["sheets"] == ["SOV"]
    assert "44 Quay Street" in xlsx["text"]


def test_nested_email_parses_one_level_then_stops():
    res = P.parse_documents([_doc("eml", "nested2.eml", "outer")])
    by_id = {d["doc_id"]: d for d in res["documents"]}
    assert by_id["outer"]["parse_status"] == "parsed"
    inner = by_id["outer-att0"]
    assert inner["filename"] == "inner.eml" and inner["parse_status"] == "parsed"
    assert "Forwarded inner" in inner["text"]
    deep = by_id["outer-att0-att0"]
    assert deep["filename"] == "data.csv"
    assert deep["parse_status"] == "failed" and "nesting" in deep["failure_reason"]


def test_email_nesting_flattens_with_parent_link():
    res = P.parse_documents([_doc("eml", "broker-email.eml", "mail-1")])
    assert res["parse"]["halted"] is False
    ids = [d["doc_id"] for d in res["documents"]]
    assert ids[0] == "mail-1"
    assert any(i.startswith("mail-1-att") for i in ids[1:])
    att = [d for d in res["documents"] if d.get("parent_doc_id") == "mail-1"]
    assert len(att) == 1 and att[0]["filename"] == "sov.csv"
    assert att[0]["parse_status"] == "parsed" and "Port Road" in att[0]["text"]


def test_corrupt_pdf_fails_explicitly_not_silently():
    out, _ = P.parse_one({"doc_id": "bad", "filename": "bad.pdf",
                          "content_bytes": b"not a pdf at all"})
    assert out["parse_status"] == "failed" and out["failure_reason"]
    res = P.parse_documents([_doc("csv", "sov.csv"),
                             {"doc_id": "bad", "filename": "bad.pdf",
                              "content_bytes": b"junk"}])
    assert res["parse"]["halted"] is False
    assert len(res["documents"]) == 2  # nothing discarded
    assert res["parse"]["failures"][0]["doc_id"] == "bad"


def test_limits():
    big = {"doc_id": "big", "filename": "big.pdf", "content_bytes": b"x" * (P.MAX_BYTES + 1)}
    out, _ = P.parse_one(big)
    assert out["parse_status"] == "failed" and "exceeds" in out["failure_reason"]
    res = P.parse_documents([{"doc_id": f"d{i}", "filename": "a.csv",
                              "content_bytes": b"a,b\n1,2\n"} for i in range(11)])
    assert res["parse"]["halted"] is True and "10" in res["parse"]["reason"]


def test_preparsed_passthrough_and_bytes_dropped():
    docs = [{"doc_id": "t", "filename": "sov.csv", "text": "already text",
             "structured_hint": {"broker_name": "Acme"},
             "content_bytes": (FIX / "csv" / "sov.csv").read_bytes()}]
    res = P.parse_documents(docs)
    d = res["documents"][0]
    assert d["parse_status"] == "parsed" and "Port Road" in d["text"]
    assert "content_bytes" not in d and d["structured_hint"]["broker_name"] == "Acme"
    untouched, _ = P.parse_one({"doc_id": "u", "text": "as-is"})
    assert untouched["parse_status"] == "pre-parsed" and untouched["text"] == "as-is"


def test_truncation_flagged():
    out, _ = P.parse_one({"doc_id": "t", "filename": "n.csv",
                          "content_bytes": ("x," * 200000).encode()})
    assert out["text_truncated"] is True and len(out["text"]) == P.MAX_TEXT_CHARS


def test_b64_input_accepted():
    raw = (FIX / "csv" / "sov.csv").read_bytes()
    out, _ = P.parse_one({"doc_id": "b", "filename": "sov.csv",
                          "content_b64": base64.b64encode(raw).decode()})
    assert out["parse_status"] == "parsed"
    bad, _ = P.parse_one({"doc_id": "b", "filename": "sov.csv", "content_b64": "a"})
    assert bad["parse_status"] == "failed"


def test_scanned_pdf_reports_ocr_pending():
    out, _ = P.parse_one(_doc("negative", "scanned.pdf"))
    assert out["parse_status"] == "ocr_pending"
    assert out["pages"] == 1
