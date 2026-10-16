"""Document parsing: formats, nesting, limits, failures (BFR-SUB-002/004/005/006/008)."""
import base64
from pathlib import Path
import pytest
from nodes import parse as P

FIX = Path(__file__).resolve().parent.parent / "samples" / "fixtures"


def _doc(name: str, doc_id: str = "d1") -> dict:
    raw = (FIX / name).read_bytes()
    return {"doc_id": doc_id, "filename": name, "content_bytes": raw}


def test_all_five_formats_parse():
    for name, needle in [("submission.pdf", "Acme Marine"),
                         ("broker-email.eml", "SOV attached"),
                         ("sov.xlsx", "Port Road"),
                         ("sov.csv", "Port Road"),
                         ("cover-note.docx", "sprinklered")]:
        out, kids = P.parse_one(_doc(name))
        assert out["parse_status"] == "parsed", (name, out)
        assert needle in out["text"], name
        assert out["text_truncated"] is False
    assert out.get("format")  # last file has format set


def test_pdf_reports_pages_xlsx_reports_sheets():
    pdf, _ = P.parse_one(_doc("submission.pdf"))
    assert pdf["pages"] == 1
    xlsx, _ = P.parse_one(_doc("sov.xlsx"))
    assert xlsx["sheets"] == ["SOV"]
    assert "44 Quay Street" in xlsx["text"]


def test_email_nesting_flattens_with_parent_link():
    res = P.parse_documents([_doc("broker-email.eml", "mail-1")])
    assert res["parse"]["halted"] is False
    ids = [d["doc_id"] for d in res["documents"]]
    assert ids[0] == "mail-1"
    assert any(i.startswith("mail-1-att") for i in ids[1:])
    att = [d for d in res["documents"] if d.get("parent_doc_id") == "mail-1"]
    assert len(att) == 1 and att[0]["filename"] == "sov.csv"
    assert att[0]["parse_status"] == "parsed" and "Port Road" in att[0]["text"]


def test_msg_unsupported_and_image_ocr_pending():
    msg, _ = P.parse_one(_doc("legacy.msg"))
    assert msg["parse_status"] == "unsupported_format" and ".msg" in msg["failure_reason"]
    png, _ = P.parse_one(_doc("scan.png"))
    assert png["parse_status"] == "ocr_pending"


def test_corrupt_pdf_fails_explicitly_not_silently():
    out, _ = P.parse_one({"doc_id": "bad", "filename": "bad.pdf",
                          "content_bytes": b"not a pdf at all"})
    assert out["parse_status"] == "failed" and out["failure_reason"]
    res = P.parse_documents([_doc("sov.csv"), {"doc_id": "bad", "filename": "bad.pdf",
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
             "content_bytes": (FIX / "sov.csv").read_bytes()}]
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
    raw = (FIX / "sov.csv").read_bytes()
    out, _ = P.parse_one({"doc_id": "b", "filename": "sov.csv",
                          "content_b64": base64.b64encode(raw).decode()})
    assert out["parse_status"] == "parsed"
    bad, _ = P.parse_one({"doc_id": "b", "filename": "sov.csv", "content_b64": "a"})
    assert bad["parse_status"] == "failed"


def test_scanned_pdf_reports_ocr_pending():
    out, _ = P.parse_one(_doc("scanned.pdf"))
    assert out["parse_status"] == "ocr_pending"
    assert out["pages"] == 1


def test_nested_email_parses_one_level_then_stops():
    res = P.parse_documents([_doc("nested2.eml", "outer")])
    by_id = {d["doc_id"]: d for d in res["documents"]}
    assert by_id["outer"]["parse_status"] == "parsed"
    inner = by_id["outer-att0"]
    assert inner["filename"] == "inner.eml" and inner["parse_status"] == "parsed"
    assert "Forwarded inner" in inner["text"]
    deep = by_id["outer-att0-att0"]
    assert deep["filename"] == "data.csv"
    assert deep["parse_status"] == "failed" and "nesting" in deep["failure_reason"]


def test_legacy_xls_unsupported():
    out, _ = P.parse_one(_doc("legacy.xls"))
    assert out["parse_status"] == "unsupported_format"
