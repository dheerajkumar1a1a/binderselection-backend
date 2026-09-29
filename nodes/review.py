"""Underwriter review: human decides, system only recommends (BFR 2.4, BFR-UWR).

Actions: accept | override | refer_back.
- override needs reason_code from the code list (BFR-UWR-005).
- hard-decline selection is blocked (BFR-UWR-007).
- identity + timestamp recorded (BFR-UWR-006).
"""
from datetime import datetime, timezone
from langgraph.types import interrupt

OVERRIDE_REASONS = [
    "PRIOR_RELATIONSHIP",
    "CAPACITY_PREFERENCE",
    "TERMS_NEGOTIATED",
    "BROKER_REQUEST",
    "OTHER",
]


def _hard_declined_rules(rule_outcomes: list[dict], rules: list[dict]) -> set[str]:
    sev = {r.get("rule_id"): r.get("severity") for r in rules}
    return {o["rule_id"] for o in rule_outcomes
            if o.get("outcome") == "Decline" and sev.get(o["rule_id"]) == "hard_decline"}


def validate(state: dict, human: dict, rules: list[dict] | None = None) -> dict:
    rules = rules or []
    action = (human or {}).get("action")
    underwriter = human.get("underwriter_id", "unknown")
    base = {"underwriter_id": underwriter,
            "decided_at": datetime.now(timezone.utc).isoformat()}
    if action == "accept":
        if state.get("recommendation", "").startswith("no eligible"):
            return {**base, "valid": False, "error": "nothing to accept"}
        return {**base, "valid": True, "action": "accept",
                "selected_binder": state.get("recommendation")}
    if action == "override":
        if human.get("reason_code") not in OVERRIDE_REASONS:
            return {**base, "valid": False, "error": "reason_code required"}
        sel = human.get("selected_binder")
        if not sel:
            return {**base, "valid": False, "error": "selected_binder required"}
        hard = _hard_declined_rules(state.get("rule_outcomes", []), rules)
        if hard and sel == state.get("recommendation", sel):
            pass
        if hard:
            return {**base, "valid": False,
                    "error": f"hard-decline blocked: {sorted(hard)}"}
        return {**base, "valid": True, "action": "override",
                "selected_binder": sel, "reason_code": human.get("reason_code"),
                "commentary": human.get("commentary", "")}
    if action == "refer_back":
        missing = ((state.get("completeness") or {}).get("missing", [])
                   + [o.get("rule_id") for o in state.get("rule_outcomes", [])
                      if o.get("outcome") == "Cannot assess"])
        return {**base, "valid": True, "action": "refer_back",
                "info_request": missing}
    return {**base, "valid": False, "error": "action must be accept|override|refer_back"}


def review(state: dict, rules: list[dict] | None = None) -> dict:
    question = {"recommendation": state.get("recommendation"),
                "binder_outcome": state.get("binder_outcome"),
                "rule_outcomes": state.get("rule_outcomes")}
    human = interrupt(question)
    decision = validate(state, human, rules)
    for _ in range(2):
        if decision.get("valid"):
            break
        human = interrupt({"error": decision.get("error"), **question})
        decision = validate(state, human, rules)
    return {"decision": decision}
