"""Lifecycle gate + source-failure safety (BFR-CAP-010, BFR-CAP-012, BFR-NFR-018)."""
from nodes.capacity import screen_safe

GOOD = {"extracted": {"total_insured_value": 100000}}


def test_active_binder_eligible():
    out = screen_safe(GOOD, 15_000_000.0, 0.0, 0.0, binder_id="binder_A")
    assert out["binder_outcome"] == "eligible"


def test_suspended_binder_excluded_with_reason():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rules"))
    from store import is_active
    reg = [{"binder_id": "binder_S", "status": "suspended",
            "effective_from": "2026-01-01", "effective_to": None}]
    assert is_active("binder_S", registry=reg) is False
    out = screen_safe(GOOD, 15_000_000.0, 0.0, 0.0, binder_id="binder_S")
    assert out["binder_outcome"] == "excluded:suspended-or-retired"


def test_unknown_binder_excluded_never_omitted():
    out = screen_safe(GOOD, 15_000_000.0, 0.0, 0.0, binder_id="binder_ZZZ")
    assert out["binder_outcome"].startswith("excluded:")
