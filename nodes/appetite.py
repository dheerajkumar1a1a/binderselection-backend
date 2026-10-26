"""Deterministic appetite evaluation (BFR-APP-004/005). No LLM here."""
# json: used to load ruleset files.
import json
# date: used for TODAY threshold resolution.
from datetime import date
# Path: filesystem paths for ruleset loading.
from pathlib import Path


# _get: resolve a field reference, supporting dotted paths into lists/dicts.
def _get(extracted: dict, ref: str):
    # Simple field (no dot) → direct lookup.
    if "." not in ref:
        return extracted.get(ref)
    # Split into head and tail.
    head, tail = ref.split(".", 1)
    val = extracted.get(head)
    # If head is a list, collect tail from each item.
    if isinstance(val, list):
        out = []
        for item in val:
            out.append(item.get(tail) if isinstance(item, dict) else None)
        return out
    # If head is a dict, get tail.
    if isinstance(val, dict):
        return val.get(tail)
    # Otherwise no value.
    return None


# _threshold: resolve special threshold tokens like "TODAY".
def _threshold(raw):
    if raw == "TODAY":
        return date.today().isoformat()
    return raw


# _single_ok: evaluate one value against one operator/threshold.
def _single_ok(val, op: str, threshold) -> bool:
    # Resolve special thresholds.
    t = _threshold(threshold)
    # Coerce threshold to match value type for numeric comparisons.
    if isinstance(val, (int, float)) and isinstance(t, str):
        try:
            t = type(val)(t)
        except (ValueError, TypeError):
            pass
    # Less-than-or-equal.
    if op == "lte":
        return val <= t
    # Strictly less.
    if op == "lt":
        return val < t
    # Greater-than-or-equal.
    if op == "gte":
        return val >= t
    # Strictly greater.
    if op == "gt":
        return val > t
    # Equality.
    if op == "eq":
        return val == t
    # Inequality.
    if op == "neq":
        return val != t
    # Membership.
    if op == "in":
        return val in t
    # Non-membership (case-insensitive on string).
    if op == "not_in":
        return str(val).upper() not in t
    # Boolean true check.
    if op == "is_true":
        return val is True
    # Boolean false check.
    if op == "is_false":
        return val is False
    # Absence check.
    if op == "is_absent":
        return val is None
    # Presence check.
    if op == "is_present":
        return val is not None
    # Date before.
    if op == "before":
        return str(val) < str(t)
    # Date after.
    if op == "after":
        return str(val) > str(t)
    # Unknown operator → error.
    raise ValueError(f"unknown-op:{op}")


# evaluate_rule: evaluate a single rule against extracted data.
def evaluate_rule(extracted: dict, rule: dict) -> dict:
    # Get the field value (supports dotted refs).
    val = _get(extracted, rule["field_reference"])
    op = rule["operator"]
    # Missing value → Cannot assess (never silent Pass).
    if val is None or val == "" or val == []:
        return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": f"missing:{rule['field_reference']}"}
    try:
        # Normalise to list for uniform handling.
        vals = val if isinstance(val, list) else [val]
        # If any element missing → Cannot assess.
        if any(v is None for v in vals):
            return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": f"missing:{rule['field_reference']}"}
        # All elements must satisfy the operator.
        ok = all(_single_ok(v, op, rule.get("threshold_value")) for v in vals)
    except (ValueError, TypeError) as e:
        return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": str(e)}
    # Return Pass if all ok, else Decline.
    return {"rule_id": rule["rule_id"], "outcome": "Pass" if ok else "Decline", "value": val}


# evaluate: entry point; loads ruleset from store or file.
def evaluate(state: dict, rules_path: str = "rules/binder_A_v1.json",
             binder_id: str | None = None, as_at: str | None = None) -> dict:
    # If binder_id given, load effective ruleset from store.
    if binder_id is not None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rules"))
        from store import load_effective
        data = load_effective(binder_id, as_at)
        rules = data["rules"]
        out = _evaluate_rules(state, rules)
        out["ruleset_version"] = data.get("version")
        return out
    # Otherwise load from file path.
    p = Path(__file__).resolve().parent.parent / Path(rules_path).name
    if not p.exists():
        p = Path(rules_path)
    rules = json.loads(p.read_text())["rules"]
    return _evaluate_rules(state, rules)


# _evaluate_rules: evaluate all rules and fold logic groups.
def _evaluate_rules(state: dict, rules: list) -> dict:
    extracted = state.get("extracted", {})
    # Evaluate each rule independently.
    outcomes = [evaluate_rule(extracted, r) for r in rules]
    # Fold logic groups (AND/OR) into combined outcomes.
    outcomes = _combine_groups(rules, outcomes, extracted)
    # Binder outcome: Decline if any Decline; Refer if any Cannot assess; else Accept.
    if any(o["outcome"] == "Decline" for o in outcomes):
        binder = "Decline"
    elif any(o["outcome"] == "Cannot assess" for o in outcomes):
        binder = "Refer"
    else:
        binder = "Accept"
    return {"rule_outcomes": outcomes, "binder_outcome": binder}


# _combine_groups: fold logic_group members into one business-rule outcome.
def _combine_groups(rules: list, outcomes: list, extracted: dict) -> list:
    # Index rules by id.
    by_id = {r.get("rule_id"): (r, o) for r, o in zip(rules, outcomes)}
    groups: dict[str, list] = {}
    order: list[str] = []
    # Collect group members and their order.
    for r in rules:
        g = r.get("logic_group")
        if g:
            groups.setdefault(g, []).append(r.get("rule_id"))
            if g not in order:
                order.append(g)
    # No groups → pass through.
    if not groups:
        return outcomes
    # Map group → logic (AND/OR).
    logic_of = {}
    for r in rules:
        if r.get("logic_group"):
            logic_of.setdefault(r["logic_group"], r.get("logic", "AND"))
    # Ungrouped rules pass through.
    folded = [o for r, o in zip(rules, outcomes) if not r.get("logic_group")]
    # Fold each group.
    for g in order:
        members = [(r, by_id[r.get("rule_id")][1]) for r in rules if r.get("logic_group") == g]
        logic = logic_of.get(g, "AND")
        # Location-scoped AND: pair per site to avoid cross-site false positives.
        if logic == "AND" and all(r.get("scope") == "location" for r, _ in members):
            combined, bitten = _per_site_and(members, extracted)
        elif logic == "OR":
            outs = [o["outcome"] for _, o in members]
            combined = "Decline" if "Decline" in outs else ("Cannot assess" if "Cannot assess" in outs else "Pass")
            bitten = [o.get("rule_id") for _, o in members if o["outcome"] == "Decline"]
        else:
            outs = [o["outcome"] for _, o in members]
            combined = "Pass" if "Pass" in outs else ("Cannot assess" if "Cannot assess" in outs else "Decline")
            bitten = [o.get("rule_id") for _, o in members if o["outcome"] == "Decline"]
        folded.append({"rule_id": g, "outcome": combined,
                       "members": [r.get("rule_id") for r, _ in members],
                       "bitten": bitten,
                       "value": [o.get("value") for _, o in members]})
    return folded


# _per_site_and: pair location-scoped AND members per site index.
def _per_site_and(members: list, extracted: dict) -> tuple[str, list]:
    locs = extracted.get("locations") or []
    n = len(locs)
    site_bites: list[int] = []
    saw_unassessable = False
    for i in range(n):
        sub = dict(extracted)
        sub["locations"] = [locs[i]]
        outs = [evaluate_rule(sub, r)["outcome"] for r, _ in members]
        if all(o == "Decline" for o in outs):
            site_bites.append(i)
        elif "Pass" not in outs:
            saw_unassessable = True
    if site_bites:
        return "Decline", [m[0].get("rule_id") for m in members]
    if saw_unassessable:
        return "Cannot assess", []
    return "Pass", []
