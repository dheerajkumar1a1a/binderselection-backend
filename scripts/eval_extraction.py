"""Live-model extraction gate (BFR-EXT-009, BFR-NFR-027).

Runs the configured extraction model over labelled fixtures and scores
per-field accuracy. Fails below threshold OR on any hallucination
(a value returned for a field labelled absent).

Usage:
    NVIDIA_API_KEY=... python scripts/eval_extraction.py \
        --fixtures scripts/eval_fixtures.json --out eval-report.json

The key travels in env only and is never printed or stored.
"""
# argparse: CLI args.
import argparse
# json: parse fixtures/report.
import json
# os: env vars.
import os
# sys: path + stderr.
import sys

# Add repo root to path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import nvidia extractor.
from nodes.extract_nvidia import nvidia_extract, DEFAULT_MODEL


# norm_commodity: normalise commodity list for comparison.
def norm_commodity(items):
    if items is None:
        return None
    return sorted(str(i.get("commodity_type", "")).upper().replace(" ", "_") for i in items)


# norm_locations: normalise location list for comparison.
def norm_locations(items):
    if items is None:
        return None
    return sorted((str(l.get("address", "")).lower().strip(), bool(l.get("sprinklered")))
                  for l in items)


# score_field: score one field; detect hallucination.
def score_field(name, got, want):
    if name in ("locations", "commodities") and got == []:
        got = None  # engine treats [] as missing; score it as absent
    if want is None:
        return ("hallucinated" if got is not None else "correct-absent",
                1.0 if got is None else 0.0)
    if got is None:
        return ("missed", 0.0)
    if name == "total_insured_value":
        try:
            ok = abs(float(got) - float(want)) < 0.01
        except (TypeError, ValueError):
            ok = False
        return ("match" if ok else "mismatch", 1.0 if ok else 0.0)
    if name == "broker_name":
        norm = lambda s: str(s).strip().lower().rstrip(".")
        ok = norm(got) == norm(want)
        return ("match" if ok else "mismatch", 1.0 if ok else 0.0)
    if name == "locations":
        ok = norm_locations(got) == norm_locations(want)
        return ("match" if ok else "mismatch", 1.0 if ok else 0.0)
    if name == "commodities":
        g, w = norm_commodity(got), norm_commodity(want)
        ok = (g == w or (g and w and (
            set(g) & set(w)
            or any(a in b or b in a for a in g for b in w))))
        return ("match" if ok else "mismatch", 1.0 if ok else 0.0)
    return ("unknown-field", 0.0)


# main: run the eval gate.
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out", default="eval-report.json")
    ap.add_argument("--threshold", type=float, default=0.8)
    args = ap.parse_args()

    if not os.environ.get("NVIDIA_API_KEY"):
        print("NVIDIA_API_KEY not set", file=sys.stderr)
        return 2
    fixtures = json.load(open(args.fixtures))["fixtures"]
    rows, scores, hallucinations = [], [], 0
    for fx in fixtures:
        ext, meta = nvidia_extract(fx["documents"])
        for field, want in fx["expected"].items():
            verdict, s = score_field(field, ext.get(field), want)
            if verdict == "hallucinated":
                hallucinations += 1
            scores.append(s)
            rows.append({"fixture": fx["id"], "field": field, "verdict": verdict,
                         "score": s, "got": ext.get(field),
                         "confidence": (meta.get(field) or {}).get("confidence")})
    overall = round(sum(scores) / len(scores), 3) if scores else 0.0
    report = {"model": DEFAULT_MODEL, "threshold": args.threshold,
              "overall": overall, "hallucinations": hallucinations,
              "passed": bool(overall >= args.threshold and hallucinations == 0),
              "rows": rows}
    json.dump(report, open(args.out, "w"), indent=1)
    print(f"model={DEFAULT_MODEL} overall={overall} hallucinations={hallucinations} "
          f"passed={report['passed']} (threshold={args.threshold})")
    for r in rows:
        print(f"  {r['fixture']}/{r['field']}: {r['verdict']} got={json.dumps(r['got'])[:100]}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
