"""Production phase 1 tests: persistent Cases + workboard + decision flow.

Doctrine under test:
- The system never decides: evaluate only recommends; a named human records
  accept/override/refer_back.
- Append-only: evaluations and decisions are never rewritten.
- Missing data halts with a named gap — never a silent Pass.
"""
import json
import os
import tempfile
from pathlib import Path

# Point the production store at a throwaway SQLite file BEFORE importing prod
# (store reads DATABASE_URL at import time). No other module imports prod.
_TMP = tempfile.mkdtemp(prefix="prod_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_TMP, "prod.sqlite3")).replace("\\", "/")

import pytest
from fastapi.testclient import TestClient

from prod import service, store, web
from prod.web import app as prod_app

from capacity import ledger as ledger_mod


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Capacity ledger isolated per-test (BINDER_LEDGER is read at runtime).
    monkeypatch.setattr(ledger_mod, "LEDGER_PATH", tmp_path / "ledger.json")
    store.init_db()
    return TestClient(prod_app, follow_redirects=True)


def _latest(case_id=None):
    with store.new_session() as s:
        q = s.query(store.Case)
        if case_id:
            q = q.filter(store.Case.case_id == case_id)
        return q.order_by(store.Case.created_at.desc()).first()


def _new_case(client, **over) -> str:
    data = {"broker_firm": "Test Broker Ltd", "underwriter": "t-uw",
            "sample_case_id": "20-demo-accept-full", "documents_json": ""}
    data.update(over)
    r = client.post("/case/new", data=data)
    assert r.status_code == 200 and "/case/" in str(r.url)
    return str(r.url).rstrip("/").split("/")[-1]


def test_workboard_and_create(client):
    r = client.get("/")
    assert r.status_code == 200 and "Workboard" in r.text
    cid = _new_case(client)
    r = client.get(f"/case/{cid}")
    assert r.status_code == 200 and r.text.count(f"{cid}") >= 1
    c = _latest(cid)
    assert c.status == "new" and c.submission_reference.startswith("PROD-")
    assert store.sla_state(c) == "due"  # fresh case → assessment SLA ticking


def test_unknown_sample_rejected(client):
    r = client.post("/case/new", data={"broker_firm": "x", "underwriter": "y",
                                       "sample_case_id": "does-not-exist"})
    assert r.status_code == 400 and "unknown sample" in r.text.lower()


def test_evaluate_accept_full_persists_append_only(client):
    cid = _new_case(client)
    r = client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    assert r.status_code == 200
    c = _latest(cid)
    assert c.status == "assessed"
    with store.new_session() as s:
        evs = s.query(store.Evaluation).filter(store.Evaluation.case_id == cid).all()
    assert len(evs) == 1
    ev = evs[0]
    payload = ev.payload
    assert "extracted_meta" in payload and "binder_results" in payload
    assert payload.get("halt") is None
    assert ev.recommendation and not ev.recommendation.startswith("no eligible")
    # Re-run: append-only — a second evaluation is added, the first untouched.
    r = client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    assert r.status_code == 200
    with store.new_session() as s:
        evs = s.query(store.Evaluation).filter(store.Evaluation.case_id == cid).all()
    assert len(evs) == 2 and evs[0].payload == evs[1].payload  # same run → same outcome


def test_full_decision_flow_reserve(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    with store.new_session() as s:
        ev = (s.query(store.Evaluation)
               .filter(store.Evaluation.case_id == cid)
               .order_by(store.Evaluation.evaluation_id.desc()).first())
        reco = ev.recommendation
    r = client.post(f"/case/{cid}/decide", data={"action": "accept",
                                                 "underwriter": "t-uw"})
    assert r.status_code == 200
    c = _latest(cid)
    assert c.status == "decided" and c.decided_at is not None
    with store.new_session() as s:
        ds = s.query(store.Decision).filter(store.Decision.case_id == cid).all()
    assert len(ds) == 1
    assert ds[0].action == "accept" and ds[0].selected_binder == reco
    assert ds[0].underwriter == "t-uw"
    assert ds[0].outcome == "reserved"  # capacity reservation happened
    page = client.get(f"/case/{cid}").text
    assert "Decision history" in page and "t-uw" in page


def test_override_requires_reason(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    with store.new_session() as s:
        b = s.query(store.Evaluation).order_by(
            store.Evaluation.evaluation_id.desc()).first().payload[
                "binder_results"][0]["binder_id"]
    # Override without a reason code is rejected by the engine — never silently.
    r = client.post(f"/case/{cid}/decide", data={"action": "override",
                                                 "underwriter": "t-uw",
                                                 "selected_binder": b})
    assert r.status_code == 400 and "reason_code required" in r.text.lower()
    with store.new_session() as s:
        assert s.query(store.Decision).filter(
            store.Decision.case_id == cid).count() == 0


def test_parse_halt_never_scores(client):
    # An unsupported document yields a halt — nothing invented, no binder scored.
    junk = {"filename": "weird.zzz", "content_b64": "aGVsbG8="}  # "hello"
    r = client.post("/case/new", data={
        "broker_firm": "Halt Broker", "underwriter": "t-uw",
        "documents_json": json.dumps([junk])})
    cid = str(r.url).rstrip("/").split("/")[-1]
    assert _latest(cid).source == "upload"
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    with store.new_session() as s:
        ev = (s.query(store.Evaluation)
               .filter(store.Evaluation.case_id == cid)
               .order_by(store.Evaluation.evaluation_id.desc()).first())
        state = ev.payload
    assert state.get("halt") in ("parse", "completeness")
    assert not state.get("binder_results")  # nothing scored past the halt
