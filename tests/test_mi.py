"""MI reports reconcile to decision records (BFR-MI acceptance)."""
from reports.mi import volume_mix, decline_reasons, override_rate, data_quality, refer_by_field

R1 = {"binder_outcome": "Accept", "extracted": {"broker_name": "Acme"},
      "decision": {"valid": True, "action": "accept", "underwriter_id": "u1"},
      "rule_outcomes": [], "extracted_meta": {}, "completeness": {}}
R2 = {"binder_outcome": "Decline", "extracted": {"broker_name": "Acme"},
      "decision": {"valid": True, "action": "override", "underwriter_id": "u2", "reason_code": "BROKER_REQUEST"},
      "rule_outcomes": [{"rule_id": "A-002-TIV", "outcome": "Decline"}],
      "extracted_meta": {}, "completeness": {}}
R3 = {"binder_outcome": "Refer", "extracted": {"broker_name": "Beta"},
      "decision": {"valid": True, "action": "refer_back", "underwriter_id": "u1"},
      "rule_outcomes": [{"rule_id": "A-002-TIV", "outcome": "Cannot assess", "reason": "missing:total_insured_value"}],
      "extracted_meta": {}, "completeness": {"missing": ["broker_name"]}}


def test_volume_mix():
    v = volume_mix([R1, R2, R3])
    assert v["total"] == 3 and v["by_outcome"]["Accept"] == 1
    assert v["by_broker"]["Acme"] == 2


def test_decline_ranked():
    assert decline_reasons([R1, R2])["by_rule"] == {"A-002-TIV": 1}


def test_override_rate_reconciles():
    o = override_rate([R1, R2, R3])
    assert o["decided"] == 3 and o["overrides"] == 1
    assert o["by_reason"] == {"BROKER_REQUEST": 1}


def test_quality_and_refer():
    assert data_quality([R3])["missing_fields"] == {"broker_name": 1}
    assert "missing:total_insured_value" in refer_by_field([R3])["by_field"]
