"""Generic maker-checker: draft proposals over versioned files, four-eyes approval.

One implementation of the proposal lifecycle, shared by every resource that needs
it (rules today, capacity next). Domain modules own three things and nothing else:

  * validation of a proposed payload
  * the shape of a version document (``build_version`` callback)
  * how two versions are compared

Everything else lives here: proposal JSON files on disk, draft -> approved
transitions, the four-eyes guard, next-version numbering, and the version file
naming convention ``<binder_id>_v<N>.json``.

Storage layout (directories supplied by the caller):

    <proposals_dir>/P-<8 hex>.json   draft and approved proposal records
    <versions_dir>/<binder_id>_v<N>.json   approved, immutable versions
"""
from __future__ import annotations

# glob: version file discovery.
import glob
# json: proposal and version documents.
import json
# os: path joining and directory creation.
import os
# uuid: proposal identifiers.
import uuid
# datetime: created_at / approved_at stamps.
from datetime import datetime


# ensure_dir: create a store directory if absent.
def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# _read: load a JSON document from disk.
def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# _write: persist a JSON document with stable formatting.
def _write(path: str, data: dict) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# version_path: the file a given version of a binder lives in.
def version_path(versions_dir: str, binder_id: str, version: int) -> str:
    return os.path.join(versions_dir, f"{binder_id}_v{version}.json")


# _version_numbers: every existing version number for a binder, sorted ascending.
def _version_numbers(versions_dir: str, binder_id: str) -> list[int]:
    nums = []
    for p in glob.glob(os.path.join(versions_dir, f"{binder_id}_v*.json")):
        stem = p.rsplit("_v", 1)[-1]
        try:
            nums.append(int(stem.split(".json")[0]))
        except ValueError:
            # A file that does not follow the convention is not a version;
            # ignore it rather than corrupting the counter.
            continue
    return sorted(nums)


# next_version: the version number an approval will write.
def next_version(versions_dir: str, binder_id: str) -> int:
    nums = _version_numbers(versions_dir, binder_id)
    return (nums[-1] if nums else 0) + 1


# current_max_version: highest existing version, or 0 when there is none.
def current_max_version(versions_dir: str, binder_id: str) -> int:
    nums = _version_numbers(versions_dir, binder_id)
    return nums[-1] if nums else 0


# list_versions: every stored version document for a binder, oldest first.
def list_versions(versions_dir: str, binder_id: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(os.path.join(versions_dir, f"{binder_id}_v*.json"))):
        out.append({"file": os.path.basename(p), "data": _read(p)})
    return out


# load_version: one version document, or an error naming what is missing.
def load_version(versions_dir: str, binder_id: str, version: int) -> dict:
    path = version_path(versions_dir, binder_id, version)
    if not os.path.exists(path):
        raise ValueError(f"version {version} not found for {binder_id}")
    return _read(path)


# proposal_path: the file a proposal lives in.
def proposal_path(proposals_dir: str, proposal_id: str) -> str:
    return os.path.join(proposals_dir, proposal_id + ".json")


# list_proposals: every proposal record, newest file order left to the caller.
def list_proposals(proposals_dir: str) -> list[dict]:
    ensure_dir(proposals_dir)
    out = []
    for fn in sorted(os.listdir(proposals_dir)):
        if not fn.endswith(".json"):
            continue
        d = _read(os.path.join(proposals_dir, fn))
        d["_file"] = fn
        out.append(d)
    return out


# get_proposal: one proposal record, or None.
def get_proposal(proposals_dir: str, proposal_id: str) -> dict | None:
    path = proposal_path(proposals_dir, proposal_id)
    if not os.path.exists(path):
        return None
    d = _read(path)
    d["_file"] = proposal_id + ".json"
    return d


# create_proposal: persist a draft. Four-eyes is checked at approval, not here,
# so any underwriter or admin may author.
def create_proposal(proposals_dir: str, binder_id: str, payload: dict, author: str,
                    effective_from: str, summary: str = "",
                    payload_key: str = "payload") -> dict:
    if not effective_from:
        raise ValueError("effective_from is required")
    proposal_id = "P-" + uuid.uuid4().hex[:8]
    proposal = {"proposal_id": proposal_id, "binder_id": binder_id,
                "status": "draft", "author": author, "approver": None,
                "effective_from": effective_from, "summary": summary,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                payload_key: payload, "approved_version": None}
    _write(proposal_path(proposals_dir, proposal_id), proposal)
    return proposal


# approve: flip a draft to approved and write the next immutable version.
# ``build_version(proposal, version, supersedes, approver)`` returns the document
# to store; the domain decides its shape, this module decides its lifecycle.
def approve(proposals_dir: str, versions_dir: str, proposal_id: str, approver: str,
            build_version, payload_key: str = "payload") -> dict:
    proposal = get_proposal(proposals_dir, proposal_id)
    if proposal is None:
        raise ValueError("proposal not found")
    if proposal.get("status") != "draft":
        raise ValueError("proposal is not in draft state")
    if approver == proposal.get("author"):
        raise ValueError("four-eyes: approver must differ from author")
    binder_id = proposal["binder_id"]
    supersedes = current_max_version(versions_dir, binder_id)
    version = next_version(versions_dir, binder_id)
    document = build_version(proposal, version, supersedes if supersedes else None,
                             approver)
    _write(version_path(versions_dir, binder_id, version), document)
    proposal["status"] = "approved"
    proposal["approver"] = approver
    proposal["approved_version"] = version
    proposal["approved_at"] = datetime.now().isoformat(timespec="seconds")
    # "_file" is a read-time annotation; never persist it back to disk.
    proposal.pop("_file", None)
    _write(proposal_path(proposals_dir, proposal_id), proposal)
    return proposal


# changed_fields: field-level before/after for flat version documents, used by
# scalar resources (capacity) whose version is a handful of named numbers.
def changed_fields(before: dict, after: dict, skip: tuple[str, ...] = ()) -> list[dict]:
    ignore = {"binder_id", "version", "effective_from", "effective_to",
              "supersedes", "author", "approver"} | set(skip)
    keys = (set(before) | set(after)) - ignore
    return [{"field": k, "before": before.get(k), "after": after.get(k)}
            for k in sorted(keys) if before.get(k) != after.get(k)]
