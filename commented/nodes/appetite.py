# Commented reference copy of nodes/appetite.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Deterministic appetite evaluation (BFR-APP-004/005). No LLM here."""
# import json
# from datetime import date
# from pathlib import Path


# def _get(extracted: dict, ref: str):
#     if "." not in ref:
#         return extracted.get(ref)
#     head, tail = ref.split(".", 1)
#     val = extracted.get(head)
#     if isinstance(val, list):
#         out = []
#         for item in val:
#             out.append(item.get(tail) if isinstance(item, dict) else None)
#         return out
#     if isinstance(val, dict):
#         return val.get(tail)
#     return None


# def _threshold(raw):
#     if raw == "TODAY":
#         return date.today().isoformat()
#     return raw


# def _single_ok(val, op: str, threshold) -> bool:
#     t = _threshold(threshold)
#     if op == "lte":
#         return val <= t
#     if op == "lt":
#         return val < t
#     if op == "gte":
#         return val >= t
#     if op == "gt":
#         return val > t
#     if op == "eq":
#         return val == t
#     if op == "neq":
#         return val != t
#     if op == "in":
#         return val in t
#     if op == "not_in":
#         return str(val).upper() not in t
#     if op == "is_true":
#         return val is True
#     if op == "is_false":
#         return val is False
#     if op == "is_absent":
#         return val is None
#     if op == "is_present":
#         return val is not None
#     if op == "before":
#         return str(val) < str(t)
#     if op == "after":
#         return str(val) > str(t)
#     raise ValueError(f"unknown-op:{op}")


# def evaluate_rule(extracted: dict, rule: dict) -> dict:
#     val = _get(extracted, rule["field_reference"])
#     op = rule["operator"]
#     if val is None or val == "" or val == []:
#         return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": f"missing:{rule['field_reference']}"}
#     try:
#         vals = val if isinstance(val, list) else [val]
#         if any(v is None for v in vals):
#             return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": f"missing:{rule['field_reference']}"}
#         ok = all(_single_ok(v, op, rule.get("threshold_value")) for v in vals)
#     except (ValueError, TypeError) as e:
#         return {"rule_id": rule["rule_id"], "outcome": "Cannot assess", "reason": str(e)}
#     return {"rule_id": rule["rule_id"], "outcome": "Pass" if ok else "Decline", "value": val}


# def evaluate(state: dict, rules_path: str = "rules/binder_A_v1.json",
#              binder_id: str | None = None, as_at: str | None = None) -> dict:
#     if binder_id is not None:
#         import sys
#         sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rules"))
#         from store import load_effective
#         data = load_effective(binder_id, as_at)
#         rules = data["rules"]
#         out = _evaluate_rules(state, rules)
#         out["ruleset_version"] = data.get("version")
#         return out
#     p = Path(__file__).resolve().parent.parent / Path(rules_path).name
#     if not p.exists():
#         p = Path(rules_path)
#     rules = json.loads(p.read_text())["rules"]
#     return _evaluate_rules(state, rules)


# def _evaluate_rules(state: dict, rules: list) -> dict:
#     extracted = state.get("extracted", {})
#     outcomes = [evaluate_rule(extracted, r) for r in rules]
#     outcomes = _combine_groups(rules, outcomes, extracted)
#     if any(o["outcome"] == "Decline" for o in outcomes):
#         binder = "Decline"
#     elif any(o["outcome"] == "Cannot assess" for o in outcomes):
#         binder = "Refer"
#     else:
#         binder = "Accept"
#     return {"rule_outcomes": outcomes, "binder_outcome": binder}


# def _combine_groups(rules: list, outcomes: list, extracted: dict) -> list:
#     """Fold logic_group members (BFR 7.4) into one business-rule outcome.

#     AND: bites only if every member bites; a single Pass clears the group;
#     otherwise Cannot-assess. OR: bites if any member bites. Ungrouped rules
#     pass through untouched. Location-scoped AND groups are paired per site:
#     the group bites only if one site trips every member — never a
#     cross-site mix (frame here + no alarm there).
#     """
#     by_id = {r.get("rule_id"): (r, o) for r, o in zip(rules, outcomes)}
#     groups: dict[str, list] = {}
#     order: list[str] = []
#     for r in rules:
#         g = r.get("logic_group")
#         if g:
#             groups.setdefault(g, []).append(r.get("rule_id"))
#             if g not in order:
#                 order.append(g)
#     if not groups:
#         return outcomes
#     logic_of = {}
#     for r in rules:
#         if r.get("logic_group"):
#             logic_of.setdefault(r["logic_group"], r.get("logic", "AND"))
#     folded = [o for r, o in zip(rules, outcomes) if not r.get("logic_group")]
#     for g in order:
#         members = [(r, by_id[r.get("rule_id")][1]) for r in rules if r.get("logic_group") == g]
#         logic = logic_of.get(g, "AND")
#         if logic == "AND" and all(r.get("scope") == "location" for r, _ in members):
#             combined, bitten = _per_site_and(members, extracted)
#         elif logic == "OR":
#             outs = [o["outcome"] for _, o in members]
#             combined = "Decline" if "Decline" in outs else ("Cannot assess" if "Cannot assess" in outs else "Pass")
#             bitten = [o.get("rule_id") for _, o in members if o["outcome"] == "Decline"]
#         else:
#             outs = [o["outcome"] for _, o in members]
#             combined = "Pass" if "Pass" in outs else ("Cannot assess" if "Cannot assess" in outs else "Decline")
#             bitten = [o.get("rule_id") for _, o in members if o["outcome"] == "Decline"]
#         folded.append({"rule_id": g, "outcome": combined,
#                        "members": [r.get("rule_id") for r, _ in members],
#                        "bitten": bitten,
#                        "value": [o.get("value") for _, o in members]})
#     return folded


# def _per_site_and(members: list, extracted: dict) -> tuple[str, list]:
#     """Pair location-scoped AND members per site index."""
#     locs = extracted.get("locations") or []
#     n = len(locs)
#     site_bites: list[int] = []
#     saw_unassessable = False
#     for i in range(n):
#         sub = dict(extracted)
#         sub["locations"] = [locs[i]]
#         outs = [evaluate_rule(sub, r)["outcome"] for r, _ in members]
#         if all(o == "Decline" for o in outs):
#             site_bites.append(i)
#         elif "Pass" not in outs:
#             saw_unassessable = True
#     if site_bites:
#         return "Decline", [m[0].get("rule_id") for m in members]
#     if saw_unassessable:
#         return "Cannot assess", []
#     return "Pass", []
