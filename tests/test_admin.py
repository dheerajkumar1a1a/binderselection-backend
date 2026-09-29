"""Rule admin: versioning, validation, four-eyes, dry-run, lifecycle."""
import pytest
from rules.store import (validate_rule, load_effective, is_active,
                         propose, approve, dry_run)


def test_validate_rejects_unknown_field_and_op():
    errs = validate_rule({"field_reference": "nope", "operator": "maybe"})
    assert any("unknown field" in e for e in errs)
    assert any("invalid operator" in e for e in errs)


def test_effective_version_loads():
    data = load_effective("binder_A", "2026-09-29")
    assert data["version"] == 1 and len(data["rules"]) == 3


def test_four_eyes_blocks_self_approval():
    p = propose({"version": 2}, author="alice")
    with pytest.raises(ValueError):
        approve(p, "alice")
    assert approve(p, "bob")["status"] == "approved"


def test_dry_run_detects_change():
    current = {"rules": [{"rule_id": "R1", "field_reference": "total_insured_value",
                          "operator": "lte", "threshold_value": 10_000_000}]}
    proposed = {"rules": [{"rule_id": "R1", "field_reference": "total_insured_value",
                           "operator": "lte", "threshold_value": 1_000_000}]}
    cases = [{"total_insured_value": 5_000_000}]
    rep = dry_run(cases, current, proposed)
    assert rep["changed"] == 1 and rep["details"][0]["before"] == "Accept"


def test_lifecycle_filters_suspended():
    assert is_active("binder_A", "2026-09-29") is True
    assert is_active("binder_B", "2026-09-29") is False
