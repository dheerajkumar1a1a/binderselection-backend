"""Leadership demo server — stdlib only, drives the real engine.

Run from the repo root:
    python ui/app.py [port]

No new dependencies. Uses the stub extractor (deterministic, no API key).
Demo writes go to ui/demo-ledger.json + audit/decisions.jsonl with UI- refs
so the MI dashboard moves live. Nothing secret is stored or served.
"""
# json: serialise responses.
import json
# os: env vars.
import os
# sys: path + stderr.
import sys
# uuid: unique refs.
import uuid
# Path: filesystem.
from pathlib import Path
# HTTP server.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# URL parsing.
from urllib.parse import urlparse, parse_qs

# ROOT: repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# Default ledger to demo-ledger.json.
os.environ.setdefault("BINDER_LEDGER", str(ROOT / "ui" / "demo-ledger.json"))

# Imports from engine.
from nodes.extract import stub_extract  # noqa: E402
from nodes import derive as drv  # noqa: E402
from nodes import completeness as comp  # noqa: E402
from nodes import multibind as mb  # noqa: E402
from nodes import narrative as nar  # noqa: E402
from nodes import review as rev  # noqa: E402
from nodes import settle as stl  # noqa: E402
from persistence import write_audit, evidence_pack  # noqa: E402
from reports import mi as mi_mod  # noqa: E402

# UI_DIR: static files.
UI_DIR = ROOT / "ui"


# _manifest: load sample manifest.
def _manifest() -> dict:
    return json.loads((ROOT / "samples" / "manifest.json").read_text(encoding="utf-8"))


# _case_by_id: fetch a case by id.
def _case_by_id(case_id: str) -> dict:
    for c in _manifest()["cases"]:
        if c["id"] == case_id:
            data = json.loads((ROOT / "samples" / "cases" / c["file"]).read_text(encoding="utf-8"))
            data["_manifest"] = c
            return data
    raise KeyError(f"unknown case {case_id}")


# run_pipeline: full path minus human pause.
def run_pipeline(documents: list, submission_ref: str, llm: str | None = None) -> dict:
    from nodes import parse as prs
    state: dict = {"submission_reference": submission_ref}
    state.update(prs.parse_documents(documents))
    if (state.get("parse") or {}).get("halted"):
        state["halt"] = "parse"
        return state
    documents = state["documents"]
    if llm == "nvidia":
        from nodes.extract import extract as extract_node
        out = extract_node({"documents": documents}, llm="nvidia")
        ext, meta = out["extracted"], out["extracted_meta"]
        state["model_versions"] = out.get("model_versions")
    elif llm == "openrouter":
        from nodes.extract import extract as extract_node
        out = extract_node({"documents": documents}, llm="openrouter")
        ext, meta = out["extracted"], out["extracted_meta"]
        state["model_versions"] = out.get("model_versions")
    else:
        ext, meta = stub_extract(documents)
    state["extracted"] = ext
    state["extracted_meta"] = meta
    state.update(drv.derive(state))
    state.update(comp.check(state))
    if not state["completeness"]["can_evaluate"]:
        state["halt"] = "completeness"
        return state
    state.update(mb.evaluate_binders(state))
    state.update(mb.rank(state))
    state.update(nar.summarize(state))
    state["halt"] = None
    return state


# decide: record underwriter decision.
def decide(run_state: dict, human: dict) -> dict:
    rulesets = run_state.get("rulesets") or {}
    selected = human.get("selected_binder") or run_state.get("recommendation")
    rules = rulesets.get(selected, [])
    decision = rev.validate(run_state, human, rules)
    if not decision.get("valid"):
        return {"decision": decision}
    state = {**run_state, "decision": decision}
    state.update(stl.settle(state))
    state.update(write_audit(state))
    record = None
    try:
        for line in (ROOT / "audit" / "decisions.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("evaluation_id") == state.get("audit_id"):
                record = r
                break
    except FileNotFoundError:
        record = None
    out = {"decision": decision, "settlement": state.get("settlement"),
           "audit_id": state.get("audit_id"), "mi": mi_mod.report()}
    if record is not None:
        out["evidence"] = evidence_pack(record)
    return out


# overview: system overview for UI.
def overview() -> dict:
    sys.path.insert(0, str(ROOT / "rules"))
    from store import load_effective
    binders = json.loads((ROOT / "rules" / "binders.json").read_text())["binders"]
    scoring = json.loads((ROOT / "rules" / "scoring.json").read_text())
    info = []
    for b in binders:
        try:
            data = load_effective(b["binder_id"])
            info.append({"binder_id": b["binder_id"], "status": b["status"],
                         "version": data.get("version"), "rules": len(data.get("rules", []))})
        except Exception as e:
            info.append({"binder_id": b["binder_id"], "status": b["status"], "error": str(e)})
    return {
        "what": "Decision-support that recommends where to place a marine cargo / stock throughput risk. The system recommends; a named underwriter decides.",
        "flow": ["Extract risk data with provenance", "Check completeness (missing -> ask broker)",
                 "Screen capacity per binder", "Evaluate appetite rules deterministically",
                 "Rank eligible binders + plain-English rationale", "Underwriter accepts, overrides, or refers back"],
        "binders": info,
        "scoring": {"weights": scoring.get("weights"), "tie_break": scoring.get("tie_break")},
        "cases": len(_manifest()["cases"]),
    }


# Handler: HTTP request handler.
class Handler(BaseHTTPRequestHandler):
    server_version = "BinderDemo/1.0"

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, (UI_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif parsed.path == "/api/overview":
            self._json(overview())
        elif parsed.path == "/api/cases":
            self._json(_manifest())
        elif parsed.path == "/api/case":
            q = parse_qs(parsed.query)
            try:
                self._json(_case_by_id(q.get("id", [""])[0]))
            except KeyError as e:
                self._json({"error": str(e)}, 404)
        elif parsed.path == "/api/mi":
            self._json(mi_mod.report())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        try:
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid JSON"}, 400)
        try:
            if parsed.path == "/api/run":
                llm = payload.get("llm")
                if llm not in (None, "nvidia", "openrouter"):
                    return self._json({"error": "llm must be 'nvidia', 'openrouter' or omitted (stub)"}, 400)
                if payload.get("case_id"):
                    case = _case_by_id(payload["case_id"])
                    docs = case["documents"]
                    ref = f"UI-{case['case_id']}-{uuid.uuid4().hex[:6]}"
                    state = run_pipeline(docs, ref, llm=llm)
                    state["dataset_expected"] = case.get("expected")
                    state["dataset_covers"] = case.get("covers")
                    self._json(state)
                elif payload.get("documents"):
                    ref = payload.get("submission_reference") or f"UI-custom-{uuid.uuid4().hex[:6]}"
                    self._json(run_pipeline(payload["documents"], ref, llm=llm))
                else:
                    self._json({"error": "pass case_id or documents"}, 400)
            elif parsed.path == "/api/decide":
                run_state = payload.get("run") or {}
                human = {k: payload.get(k) for k in
                         ("action", "underwriter_id", "selected_binder", "reason_code", "commentary")
                         if payload.get(k) is not None}
                if not run_state or not human.get("action"):
                    return self._json({"error": "pass run + action"}, 400)
                human.setdefault("underwriter_id", "ui-underwriter")
                self._json(decide(run_state, human))
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def log_message(self, fmt, *args):
        sys.stderr.write("binder-ui: %s\n" % (fmt % args,))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8080"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Binder Selection Agent — leadership demo at http://127.0.0.1:{port} (Ctrl+C to stop)")
    srv.serve_forever()
