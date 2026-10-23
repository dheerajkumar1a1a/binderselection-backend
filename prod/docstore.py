"""Document store (phase 2): uploaded/pinned documents live on disk, per case.

Layout (local-first, one case = one folder):

    data/cases/<case_id>/manifest.json   # what arrived
    data/cases/<case_id>/docs/<doc_id>__<filename>   # raw bytes, when any

manifest.json documents: one entry per original document, preserving the
exact dict that was handed to the pipeline (sample docs carry
`text`/`structured_hint`; uploads carry content_bytes, which live in the
docs/ folder and are re-attached at evaluation time). Nothing is ever
mutated after write - the manifest is append-ish (rewritten only to decode
failures is NOT done; parse failures stay failures and surface as halts).

Provenance doctrine: the viewer opens the document; the highlight is a
display feature over stored text, never an editor.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data", "cases")


def case_dir(case_id: str) -> str:
    return os.path.join(BASE, case_id)


def _safe_doc_id(doc_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_. " else "_" for c in (doc_id or "doc"))


def save_docs(case_id: str, docs: list[dict]) -> None:
    """Persist the documents that opened a Case (bytes where present)."""
    d = case_dir(case_id)
    os.makedirs(os.path.join(d, "docs"), exist_ok=True)
    entries = []
    for doc in docs:
        entry = {k: v for k, v in doc.items() if k != "content_bytes"}
        data = doc.get("content_bytes")
        if data:
            name = f"{_safe_doc_id(doc.get('doc_id'))}__{doc.get('filename') or 'file'}"
            with open(os.path.join(d, "docs", name), "wb") as f:
                f.write(data)
            entry["stored_file"] = name
        entries.append(entry)
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"case_id": case_id, "documents": entries}, f, indent=2)


def load_run_docs(case_id: str) -> list[dict]:
    """Re-build the exact document payloads the pipeline received at intake."""
    with open(os.path.join(case_dir(case_id), "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    docs = []
    for e in man["documents"]:
        doc = {k: v for k, v in e.items() if k != "stored_file"}
        if e.get("stored_file"):
            with open(os.path.join(case_dir(case_id), "docs", e["stored_file"]), "rb") as f:
                doc["content_bytes"] = f.read()
        docs.append(doc)
    return docs


def manifest_text(case_id: str) -> dict[str, dict]:
    """doc_id -> manifest entry (fallback text/status before any evaluation)."""
    try:
        with open(os.path.join(case_dir(case_id), "manifest.json"), encoding="utf-8") as f:
            return {d["doc_id"]: d for d in json.load(f)["documents"]}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
