"""Deterministic appetite evaluation (BFR-APP-004/005). No LLM here."""
import json
from datetime import date
from pathlib import Path


def _get(extracted: dict, ref: str):
    if "." not in ref:
        return extracted.get(ref)
    head, tail = ref.split(".", 1)
    val = extracted.get(head)
    if isinstance(val, list):
        out = []
        for item in val:
            out.append(item.get(tail) if isinstance(item, dict) else None)
        return out
    if isinstance(val, dict):
        return val.get(tail)
    return None


def _threshold(raw):
    if raw == "TODAY":
        return date.today().isoformat()
    return raw


def _single_ok(val, op: str, threshold) -> bool:
    t = _threshold(threshold)
    if op == "lte":
        return val <= t
    if op == "lt":
        return val < t
    if op == "gte":
        return val >= t
    if op == "gt":
        return val > t
    if op == "eq":
        return val == t
    if op == "neq":
        return val != t
    if op == "in":
        return val in t
    if op == "not_in":
        return str(val).upper() not in t
    if op == "is_true":
        return val is True
    if op == "is_false":
        return val is False
    if op == "is_absent":
        return val is None
    if op == "is_present":
        return val is not None
    if op == "before":
        return str(val) < str(t)
    if op == "after":
        return str(val) > str(t)
    raise ValueError(f"unknown-op:{op}")


def evaluate_rule(extracted: dict, rule: dict) -> dict:
    val = _get(extracted, rule["field_reference"])
    op = rule["operator"]
    if val is None or val == "" or val == []:
        return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": f"missing:{rule['field_reference']}"}
    try:
        vals = val if isinstance(val, list) else [val]
        if any(v is None for v in vals):
            return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": f"missing:{rule['field_reference']}"}
        ok = all(_single_ok(v, op, rule.get("threshold_value")) for v in vals)
    except (ValueError, TypeError) as e:
        return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": str(e)}
    return {"rule_id": rule["rule_id"], "outcome": "Pass" if ok else "Decline", "value": val}


def evaluate(state: dict, rules_path: str = "rules/binder_A_v1.json",
             binder_id: str | None = None, as_at: str | None = None) -> dict:
    if binder_id is not None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rules"))
        from store import load_effective
        data = load_effective(binder_id, as_at)
        rules = data["rules"]
        out = _evaluate_rules(state, rules)
        out["ruleset_version"] = data.get("version")
        return out
    p = Path(__file__).resolve().parent.parent / Path(rules_path).name
    if not p.exists():
        p = Path(rules_path)
    rules = json.loads(p.read_text())["rules"]
    return _evaluate_rules(state, rules)


def _evaluate_rules(state: dict, rules: list) -> dict:
    extracted = state.get("extracted", {})
    outcomes = [evaluate_rule(extracted, r) for r in rules]
    if any(o["outcome"] == "Decline" for o in outcomes):
        binder = "Decline"
    elif any(o["outcome"] == "Cannot assess" for o in outcomes):
        binder = "Refer"
    else:
        binder = "Accept"
    return {"rule_outcomes": outcomes, "binder_outcome": binder}
