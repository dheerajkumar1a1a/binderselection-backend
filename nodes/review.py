"""Underwriter review: human decides, system only recommends (BFR 2.4, BFR-UWR).

Actions: accept | override | refer_back | correct.
- override needs reason_code from the code list (BFR-UWR-005).
- hard-decline selection is blocked (BFR-UWR-007).
- correct resolves contested values and triggers re-evaluation (BFR-EXT-006/007).
- identity + timestamp recorded (BFR-UWR-006).
"""
# datetime: timestamp for decision.
from datetime import datetime, timezone
# interrupt: LangGraph human-in-the-loop pause.
from langgraph.types import interrupt

# OVERRIDE_REASONS: allowed reason codes for override.
OVERRIDE_REASONS = [
    "PRIOR_RELATIONSHIP",
    "CAPACITY_PREFERENCE",
    "TERMS_NEGOTIATED",
    "BROKER_REQUEST",
    "OTHER",
]


# _hard_declined_rules: collect rule ids that hard-declined.
def _hard_declined_rules(rule_outcomes: list[dict], rules: list[dict]) -> set[str]:
    # Map rule id → severity.
    sev = {r.get("rule_id"): r.get("severity") for r in rules}
    # Return set of hard-decline rule ids that actually declined.
    return {o["rule_id"] for o in rule_outcomes
            if o.get("outcome") == "Decline" and sev.get(o["rule_id"]) == "hard_decline"}


# validate: validate an underwriter action.
def validate(state: dict, human: dict, rules: list[dict] | None = None) -> dict:
    rules = rules or []
    action = (human or {}).get("action")
    underwriter = human.get("underwriter_id", "unknown")
    # Base record with identity + timestamp.
    base = {"underwriter_id": underwriter,
            "decided_at": datetime.now(timezone.utc).isoformat()}
    # Accept: recommendation must exist.
    if action == "accept":
        if state.get("recommendation", "").startswith("no eligible"):
            return {**base, "valid": False, "error": "nothing to accept"}
        return {**base, "valid": True, "action": "accept",
                "selected_binder": state.get("recommendation")}
    # Override: requires reason_code and selected_binder; blocks hard-decline.
    if action == "override":
        if human.get("reason_code") not in OVERRIDE_REASONS:
            return {**base, "valid": False, "error": "reason_code required"}
        sel = human.get("selected_binder")
        if not sel:
            return {**base, "valid": False, "error": "selected_binder required"}
        hard = _hard_declined_rules(state.get("rule_outcomes", []), rules)
        if hard:
            return {**base, "valid": False,
                    "error": f"hard-decline blocked: {sorted(hard)}"}
        return {**base, "valid": True, "action": "override",
                "selected_binder": sel, "reason_code": human.get("reason_code"),
                "commentary": human.get("commentary", "")}
    # Refer back: build info request list.
    if action == "refer_back":
        missing = list((state.get("completeness") or {}).get("missing", []))
        for r in state.get("binder_results", []):
            missing += [o.get("rule_id") for o in r.get("rule_outcomes", [])
                        if o.get("outcome") == "Cannot assess"]
        missing += [o.get("rule_id") for o in state.get("rule_outcomes", [])
                    if o.get("outcome") == "Cannot assess"]
        return {**base, "valid": True, "action": "refer_back",
                "info_request": sorted(set(missing))}
    # Correct: requires corrections dict.
    if action == "correct":
        corrections = human.get("corrections") or {}
        if not corrections:
            return {**base, "valid": False, "error": "corrections required"}
        return {**base, "valid": True, "action": "correct",
                "corrections": corrections}
    # Unknown action.
    return {**base, "valid": False, "error": "action must be accept|override|refer_back|correct"}


# _rules_for: resolve which ruleset applies to the selected binder.
def _rules_for(state: dict, human: dict, rules: list[dict] | None) -> list[dict]:
    if rules is not None:
        return rules
    rulesets = state.get("rulesets") or {}
    selected = (human or {}).get("selected_binder") or state.get("recommendation")
    return rulesets.get(selected, [])


# review: LangGraph node that pauses for human decision.
def review(state: dict, rules: list[dict] | None = None) -> dict:
    meta = state.get("extracted_meta") or {}
    # Collect contested fields for the question.
    contested = {f: m.get("conflict") for f, m in meta.items()
                 if isinstance(m, dict) and m.get("contested")}
    # Build the interrupt question payload.
    question = {"recommendation": state.get("recommendation"),
                "ranking": state.get("ranking"),
                "narrative": state.get("narrative"),
                "binder_outcome": state.get("binder_outcome"),
                "parse_failures": ((state.get("parse") or {}).get("failures") or []),
                "contested": contested,
                "binder_results": [
                    {"binder_id": r.get("binder_id"), "outcome": r.get("outcome"),
                     "reason": r.get("reason"),
                     "ruleset_version": r.get("ruleset_version")}
                    for r in state.get("binder_results", [])],
                "rule_outcomes": state.get("rule_outcomes")}
    # Pause for human input.
    human = interrupt(question)
    decision = validate(state, human, _rules_for(state, human, rules))
    # Allow up to 2 retries on invalid input.
    for _ in range(2):
        if decision.get("valid"):
            break
        human = interrupt({"error": decision.get("error"), **question})
        decision = validate(state, human, _rules_for(state, human, rules))
    # If correct action, apply corrections and re-evaluate.
    if decision.get("action") == "correct":
        from nodes import correct as corr
        fixed = corr.apply(state, decision["corrections"], decision["underwriter_id"])
        return {"decision": decision, **fixed}
    return {"decision": decision}
