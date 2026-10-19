"""Run one Gemini extraction for a CI request (the repo-secret path).

The Pages demo dispatches .github/workflows/extract-request.yml with a
gzip+base64 payload. This script decodes it, runs the shared Gemini extractor
(nodes/extract_gemini.py, key from GEMINI_API_KEY - the repo secret in CI), and
writes a result JSON the page polls. The model reads; it never decides.

Inputs (env, so nothing is interpolated into a shell):
  PAYLOAD_GZ_B64  gzip+base64 of {"documents": [{"doc_id","filename","text"}], "model": str}
  REQUEST_ID      8-32 lowercase hex, produced by the page

Output: docs/data/extract-results/<REQUEST_ID>.json
  {"ok": true,  "request_id", "model", "documents", "extracted", "meta", "completed_at"}
  {"ok": false, "request_id", "error", "completed_at"}

Nothing but the output path is printed: document text must never reach the logs
(the dispatch inputs are public anyway, but we do not add to that).
"""
# argparse: CLI.
import argparse
# base64/gzip: payload codec.
import base64
import gzip
# json: payload + result.
import json
# os/sys: env + import path.
import os
import sys
# re: validate the request id before it becomes a file name.
import re
# datetime: completion stamp.
from datetime import datetime, timezone

# Make the repo root importable (nodes.*).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# A request id must be lowercase hex so it can never escape the output directory.
ID_RE = re.compile(r"^[0-9a-f]{8,32}$")


# decode_payload: gzip+base64 -> dict.
def decode_payload(b64: str) -> dict:
    raw = gzip.decompress(base64.b64decode(b64))
    return json.loads(raw.decode("utf-8"))


# main: read the request, extract, write the result. Always exits 0 so the job
# can commit an error result (the page then stops polling instead of hanging).
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request-id", default=os.environ.get("REQUEST_ID"))
    ap.add_argument("--payload-gz-b64", default=os.environ.get("PAYLOAD_GZ_B64"))
    ap.add_argument("--out", default=None, help="override output path (tests)")
    args = ap.parse_args(argv)

    request_id = (args.request_id or "").strip()
    if not ID_RE.match(request_id):
        print(f"invalid request id (expected 8-32 lowercase hex): {request_id!r}")
        return 2
    out = args.out or os.path.join(ROOT, "docs", "data", "extract-results", request_id + ".json")

    result = {"request_id": request_id,
              "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        payload = decode_payload(args.payload_gz_b64 or "")
        documents = payload.get("documents") or []
        if not isinstance(documents, list):
            raise ValueError("payload.documents must be a list")
        model = payload.get("model") or None
        # Imported lazily so a decode error is reported before touching the API.
        from nodes.extract_gemini import DEFAULT_MODEL, gemini_extract
        extracted, meta = gemini_extract(documents, model=model)
        result.update({"ok": True, "model": model or DEFAULT_MODEL,
                       "documents": len(documents),
                       "extracted": extracted, "meta": meta})
    except Exception as e:  # noqa: BLE001 - report, never raise into a red job
        result.update({"ok": False, "error": f"{type(e).__name__}: {e}"})

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
    # Deliberately no document text / field values here.
    print(f"wrote {out} ok={result['ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
