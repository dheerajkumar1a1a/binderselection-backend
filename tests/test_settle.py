"""Ledger: idempotent reserve, over-line block, bind/cancel write-back."""
import os
import capacity.ledger as L


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("BINDER_LEDGER", str(tmp_path / "ledger.json"))
    L.LEDGER_PATH = tmp_path / "ledger.json"


def test_reserve_idempotent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    r1 = L.reserve("binder_A", "SUB-1", 1_000_000)
    r2 = L.reserve("binder_A", "SUB-1", 1_000_000)
    assert r1["deduped"] is False and r2["deduped"] is True
    assert r1["reservation_id"] == r2["reservation_id"]


def test_overline_blocked(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    try:
        L.reserve("binder_A", "SUB-BIG", 999_999_999_999)
        assert False, "should have raised"
    except ValueError as e:
        assert "insufficient capacity" in str(e)


def test_bind_and_cancel(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    L.reserve("binder_A", "SUB-2", 2_000_000)
    b1 = L.bind("binder_A", "SUB-2", 2_000_000)
    b2 = L.bind("binder_A", "SUB-2", 2_000_000)
    assert b1["deduped"] is False and b2["deduped"] is True
    c = L.cancel("binder_A", "SUB-2", 2_000_000)
    assert c["cancelled"] is True


def test_release_frees_capacity(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    before = L.available("binder_A")
    L.reserve("binder_A", "SUB-3", 3_000_000)
    assert L.available("binder_A") < before
    L.release("SUB-3", "binder_A")
    assert L.available("binder_A") == before
