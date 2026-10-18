"""MI reports from decision records (BFR-MI-001..005, 007).

Reads audit/decisions.jsonl. Pure functions over records for testability.
Stage timing (MI-006) needs stage-duration instrumentation - reported as
gap until nodes emit timings.
"""
# json: parse audit records.
import json
# Counter: count occurrences.
from collections import Counter
# Path: filesystem paths.
from pathlib import Path

# BASE: repo root.
BASE = Path(__file__).resolve().parent.parent


# load: read audit records from jsonl.
def load(path: str | Path | None = None) -> list[dict]:
    p = Path(path) if path else BASE / "audit" / "decisions.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


# volume_mix: volume by outcome/broker/underwriter.
def volume_mix(records: list[dict]) -> dict:
    # Derive outcome from record.
    def _outcome(r: dict):
        if r.get("binder_outcome"):
            return r["binder_outcome"]
        if (r.get("recommendation") or "").startswith("no eligible"):
            return "Decline"
        if r.get("recommendation"):
            return "Accept"
        return None
    return {
        "total": len(records),
        "by_outcome": dict(Counter(_outcome(r) for r in records)),
        "by_broker": dict(Counter((r.get("extracted") or {}).get("broker_name") for r in records)),
        "by_underwriter": dict(Counter((r.get("decision") or {}).get("underwriter_id") for r in records)),
    }


# decline_reasons: count declines by rule.
def decline_reasons(records: list[dict]) -> dict:
    c: Counter = Counter()
    for r in records:
        for o in r.get("rule_outcomes") or []:
            if o.get("outcome") == "Decline":
                c[o.get("rule_id")] += 1
    return {"by_rule": dict(c.most_common())}


# override_rate: override statistics.
def override_rate(records: list[dict]) -> dict:
    decided = [r for r in records if (r.get("decision") or {}).get("valid")]
    overrides = [r for r in decided if r["decision"].get("action") == "override"]
    reasons = Counter(r["decision"].get("reason_code") for r in overrides)
    return {"decided": len(decided), "overrides": len(overrides),
            "rate": len(overrides) / len(decided) if decided else 0.0,
            "by_reason": dict(reasons)}


# data_quality: data quality metrics.
def data_quality(records: list[dict]) -> dict:
    missing = Counter()
    low_conf = 0
    for r in records:
        for f in ((r.get("completeness") or {}).get("missing")) or []:
            missing[f] += 1
        for m in ((r.get("extracted_meta") or {}).values()):
            if isinstance(m, dict) and m.get("present") and m.get("confidence", 1.0) < 0.5:
                low_conf += 1
    info_requests = sum(1 for r in records if (r.get("decision") or {}).get("action") == "refer_back")
    return {"missing_fields": dict(missing.most_common()),
            "low_confidence_fields": low_conf,
            "info_requests": info_requests}


# refer_by_field: count Cannot-assess by field.
def refer_by_field(records: list[dict]) -> dict:
    c: Counter = Counter()
    for r in records:
        for o in r.get("rule_outcomes") or []:
            if o.get("outcome") == "Cannot assess":
                c[o.get("reason", o.get("rule_id"))] += 1
    return {"by_field": dict(c.most_common())}


# report: aggregate MI report.
def report(path: str | Path | None = None) -> dict:
    records = load(path)
    return {"volume_mix": volume_mix(records),
            "decline_reasons": decline_reasons(records),
            "override_rate": override_rate(records),
            "data_quality": data_quality(records),
            "refer_by_field": refer_by_field(records),
            "stage_timing": stage_timing(records)}


# stage_timing: mean seconds per stage.
def stage_timing(records: list[dict]) -> dict:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for r in records:
        for stage, secs in (r.get("stage_timings") or {}).items():
            sums[stage] = sums.get(stage, 0.0) + float(secs)
            counts[stage] = counts.get(stage, 0) + 1
    if not counts:
        return {"gap": "no timed records yet"}
    return {"mean_seconds": {s: round(sums[s] / counts[s], 4) for s in sums},
            "n": len(records)}
