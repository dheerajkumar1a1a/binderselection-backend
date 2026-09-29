"""Review gate: accept / override guardrails / hard-decline block / refer_back."""
from nodes.review import validate

BASE = {"recommendation": "binder_A", "binder_outcome": "Accept",
        "rule_outcomes": [], "completeness": {"missing": []}}


def test_accept():
    d = validate(BASE, {"action": "accept", "underwriter_id": "u1"})
    assert d["valid"] and d["selected_binder"] == "binder_A"
    assert d["underwriter_id"] == "u1" and "decided_at" in d


def test_override_needs_reason():
    d = validate(BASE, {"action": "override", "selected_binder": "binder_B",
                        "underwriter_id": "u1"})
    assert not d["valid"]


def test_override_ok_with_reason():
    d = validate(BASE, {"action": "override", "selected_binder": "binder_B",
                        "reason_code": "BROKER_REQUEST", "underwriter_id": "u1"})
    assert d["valid"] and d["reason_code"] == "BROKER_REQUEST"


def test_hard_decline_blocked():
    state = {**BASE, "rule_outcomes": [{"rule_id": "R1", "outcome": "Decline"}]}
    rules = [{"rule_id": "R1", "severity": "hard_decline"}]
    d = validate(state, {"action": "override", "selected_binder": "binder_A",
                         "reason_code": "OTHER", "underwriter_id": "u1"}, rules)
    assert not d["valid"] and "hard-decline" in d["error"]


def test_refer_back_lists_missing():
    state = {**BASE, "completeness": {"missing": ["loss_run_provided"]}}
    d = validate(state, {"action": "refer_back", "underwriter_id": "u1"})
    assert d["valid"] and "loss_run_provided" in d["info_request"]
