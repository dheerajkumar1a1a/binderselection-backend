"""Multi-binder evaluation: one engine, N rulesets (BFR-APP-011, BFR-REC).

Binders are data, never agents: each active binder's effective ruleset is
loaded from the store and evaluated independently — no binder's outcome
influences another's. Scoring is absolute per binder (BFR-REC-005) from
`rules/scoring.json`; ties break by the configured order (BFR-REC-006,
OPEN-5 default).
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _load_json(name: str) -> dict:
    return json.loads((BASE / "rules" / name).read_text())


def active_binders(as_at: str | None = None) -> list[dict]:
    import sys
    sys.path.insert(0, str(BASE / "rules"))
    from store import is_active
    return [b for b in _load_json("binders.json")["binders"]
            if is_active(b["binder_id"], as_at)]


def capacity_for(binder_id: str) -> dict:
    caps = _load_json("capacity.json")["binders"]
    if binder_id not in caps:
        raise KeyError(f"no capacity record for {binder_id} (BFR-CAP-012)")
    return caps[binder_id]


def evaluate_binders(state: dict, binder_ids: list[str] | None = None,
                     as_at: str | None = None) -> dict:
    """Graph node when called with state only: evaluates all active binders."""
    import sys
    sys.path.insert(0, str(BASE / "rules"))
    from store import load_effective
    from nodes import capacity as cap
    from nodes import appetite as app
    extracted = state.get("extracted", {})
    if binder_ids is None:
        binder_ids = [b["binder_id"] for b in active_binders(as_at)]
    results = []
    rulesets = {}
    for bid in binder_ids:
        try:
            cap_cfg = capacity_for(bid)
            cout = cap.screen_safe({"extracted": extracted},
                                   cap_cfg["authorised_line"],
                                   cap_cfg["written_to_date"],
                                   cap_cfg.get("reserved", 0.0),
                                   binder_id=bid, as_at=as_at)
        except Exception as e:
            results.append({"binder_id": bid, "outcome": "failed",
                            "reason": f"{type(e).__name__}:{e}"})
            continue
        if cout["binder_outcome"] != "eligible":
            results.append({"binder_id": bid, "outcome": "excluded",
                            "reason": cout["binder_outcome"],
                            "capacity_snapshot": cout["capacity_snapshot"]})
            continue
        data = load_effective(bid, as_at)
        rulesets[bid] = data["rules"]
        aout = app._evaluate_rules({"extracted": extracted}, data["rules"])
        results.append({"binder_id": bid, "outcome": aout["binder_outcome"],
                        "rule_outcomes": aout["rule_outcomes"],
                        "ruleset_version": data.get("version"),
                        "capacity_snapshot": cout["capacity_snapshot"]})
    return {"binder_results": results, "rulesets": rulesets}


def score_binders(results: list[dict], registry: list[dict] | None = None) -> dict:
    scoring = _load_json("scoring.json")
    w = scoring["weights"]
    reg = {b["binder_id"]: b for b in (registry or _load_json("binders.json")["binders"])}
    scored = []
    for r in results:
        if r["outcome"] != "Accept":
            continue
        snap = r.get("capacity_snapshot") or {}
        line = snap.get("authorised_line") or 1.0
        avail = snap.get("available_capacity") or 0.0
        parts = {
            "available_capacity": round(w["available_capacity"] * avail / line, 3),
            "strategic_classification": scoring["strategic_points"].get(
                reg.get(r["binder_id"], {}).get("strategic_classification"), 0),
            "appetite_fit": w["appetite_fit"],
        }
        scored.append({"binder_id": r["binder_id"], "parts": parts,
                       "total": round(sum(parts.values()), 3),
                       "available_capacity": avail})
    tie = scoring.get("tie_break", [])
    def _key(s: dict):
        keys: list = [-s["total"]]
        for k in tie:
            v = s.get(k, s["binder_id"])
            keys.append(-v if isinstance(v, (int, float)) else str(v))
        return tuple(keys)
    scored.sort(key=_key)
    if not scored:
        return {"scores": {}, "score_parts": {}, "ranking": [],
                "recommendation": "no eligible binder"}
    return {"scores": {s["binder_id"]: s["total"] for s in scored},
            "score_parts": {s["binder_id"]: s["parts"] for s in scored},
            "ranking": [s["binder_id"] for s in scored],
            "recommendation": scored[0]["binder_id"]}


def rank(state: dict) -> dict:
    """Graph node: absolute cross-binder ranking from evaluation results."""
    return score_binders(state.get("binder_results", []))
