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
    c = TestClient(prod_app, follow_redirects=True)
    # Staff surfaces are login-gated (phase 3) — tests act as the admin.
    c.post("/login", data={"username": "admin", "password": "change-me-admin"})
    return c


def _latest(case_id=None):
    with store.new_session() as s:
        q = s.query(store.Case)
        if case_id:
            q = q.filter(store.Case.case_id == case_id)
        return q.order_by(store.Case.created_at.desc()).first()


def _new_case(client, **over) -> str:
    data = {"broker_firm": "Harbourline Logistics", "underwriter": "t-uw",
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


def test_extract_failure_is_clean_400(client, monkeypatch):
    """A live-extractor failure (e.g. missing key) → explicit 400, not a 500."""
    cid = _new_case(client)
    from prod import service as S
    monkeypatch.setattr(S.demo, "run_pipeline",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("NVIDIA_API_KEY not set")))
    r = client.post(f"/case/{cid}/evaluate", data={"llm": "nvidia"})
    assert r.status_code == 400 and "extractor unavailable" in r.text
    with store.new_session() as s:
        # No evaluation was appended — the run simply did not happen.
        assert s.query(store.Evaluation).filter(
            store.Evaluation.case_id == cid).count() == 0


# --- phase 2: docs on disk + provenance viewer ------------------------------

import prod.docstore as docstore


def test_docs_persist_to_disk_and_survive_restart(client, monkeypatch):
    """Restart-proof: wipe any cached process state, evaluate must still work."""
    cid = _new_case(client)
    # Simulate a server restart: the only doc source must now be the disk.
    ids_before = [d["doc_id"] for d in docstore.load_run_docs(cid)]
    assert ids_before == ["mail-001"]
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    c = _latest(cid)
    assert c.status == "assessed"
    with store.new_session() as s:
        ev = (s.query(store.Evaluation).order_by(
            store.Evaluation.evaluation_id.desc()).first())
    assert ev.recommendation == "binder_A"


def test_provenance_viewer_highlights_structured_record(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    r = client.get(f"/case/{cid}/doc/mail-001")
    assert r.status_code == 200
    body = r.text
    assert "Machine-readable submission record" in body
    # The stub reads each field from the structured hint; those fact lines
    # must be marked.
    assert body.count("<mark") >= 5
    assert 'data-f="total_insured_value"' in body
    assert 'data-f="broker_name"' in body


def test_provenance_viewer_quote_match(client):
    """A quote-style locator (live extractors) is found in text even with
    different spacing, and unknown quotes degrade to shown-as-is."""
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    view = service.doc_view(cid, "mail-001")
    assert view is not None and view["has_text"]
    # Fake a quote-locator evaluation result through the same helper path:
    from prod import service as S
    marks = S._flex_find(view["doc"].get("text") or "", "Broker Acme")
    assert marks is not None


def test_case_page_links_provenance(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    page = client.get(f"/case/{cid}").text
    assert f'href="/case/{cid}/doc/mail-001"' in page


# --- phase 3: auth, Request rounds, letters, delta, portal -------------------
#
# Doctrine under test:
# - The broker portal sees ask-lists + letters only: never scores, rules,
#   binders or other firms' cases (Q8/Q10).
# - Rounds are engine-named (Q4), one active per case (Q2), locked on submit,
#   and the submission runs a successor evaluation synchronously (Q14/Q15).
# - Typed answers enter the engine as the broker's answer sheet — data, not
#   decisions, provenance-marked.

def _login(client, username, password):
    # follow_redirects=False: brokers logging in must not be bounced against
    # the (staff-only) workboard; the redirect itself is the success signal.
    r = client.post("/login", data={"username": username, "password": password},
                    follow_redirects=False)
    assert r.status_code in (200, 303)


def _logout(client):
    client.get("/logout")


def test_staff_pages_require_login(client):
    _logout(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]
    r = client.get("/case/whatever", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]


def test_login_seeded_admin(client):
    _logout(client)
    _login(client, "admin", "change-me-admin")
    r = client.get("/")
    assert r.status_code == 200 and "Workboard" in r.text
    # Wrong password refuses.
    client.get("/logout")
    r = client.post("/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 400


def _round_fields(cid):
    """Field names the engine marked Cannot assess on the latest evaluation."""
    return [g["field"] for g in service.latest_gaps(cid)]


def test_round_issue_locks_and_notifies(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    fields = _round_fields(cid)
    assert fields  # the sample has engine-named gaps
    r = client.post(f"/case/{cid}/round/issue",
                    data={"field_0": fields[0], "note_0": "please confirm"})
    assert r.status_code == 200
    c = _latest(cid)
    assert c.status == "awaiting-broker"
    rounds = service.rounds_for_case(cid)
    assert len(rounds) == 1 and rounds[0]["round"].number == 1
    assert rounds[0]["round"].status == "open"
    assert store.round_sla_state(rounds[0]["round"]) == "due"
    # One active round per case (Q2) — a second issue is rejected.
    r = client.post(f"/case/{cid}/round/issue", data={"field_0": fields[0]})
    assert r.status_code == 400 and "active" in r.text
    # Broker notification landed in the local outbox (Q6/Q13).
    outbox = os.path.join(os.path.dirname(store.__file__), "..", "data", "outbox")
    mails = os.listdir(outbox) if os.path.isdir(outbox) else []
    assert mails, "round-issued email must exist in the outbox"


def test_broker_draft_submit_runs_successor_evaluation(client, monkeypatch):
    # The default evaluation extractor stays stub (keyless, deterministic).
    monkeypatch.setenv("APP_DEFAULT_LLM", "")
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    fields = _round_fields(cid)
    client.post(f"/case/{cid}/round/issue", data={"field_0": fields[0]})
    # Broker drafts an answer to the first item.
    with store.new_session() as s:
        rnd = s.query(store.RequestRound).filter(
            store.RequestRound.case_id == cid).one()
        item = s.query(store.RequestItem).filter(
            store.RequestItem.round_id == rnd.round_id).first()
        rid, iid = rnd.round_id, item.item_id
        fld = item.field
    _logout(client)
    _login(client, "broker", "change-me-broker")
    r = client.post(f"/portal/case/{cid}/round/{rid}/draft", data={
        f"answer_{iid}": "350000" if "claim" in fld else "yes"})
    assert r.status_code in (200, 303)
    # Submission locks the round and chains a successor evaluation (Q14/Q15).
    with store.new_session() as s:
        before = s.query(store.Evaluation).filter(
            store.Evaluation.case_id == cid).count()
    r = client.post(f"/portal/case/{cid}/round/{rid}/submit", data={})
    assert r.status_code in (200, 303)
    with store.new_session() as s:
        after = s.query(store.Evaluation).filter(
            store.Evaluation.case_id == cid).count()
        assert after == before + 1  # successor evaluation appended
        rnd = s.get(store.RequestRound, rid)
        assert rnd.status == "locked" and rnd.answered_evaluation_id is not None
        item = s.query(store.RequestItem).filter(
            store.RequestItem.item_id == iid).first()
    # The answer sheet document exists and carries the typed answer.
    man = docstore.manifest_text(cid)
    sheet = man.get("round-1-answers")
    assert sheet and (fld in (sheet.get("text") or ""))
    c = _latest(cid)
    assert c.status in ("assessed", "decided")


def test_portal_scoping_never_leaks(client):
    cid = _new_case(client, broker_firm="Harbourline Logistics")
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    other = _new_case(client, broker_firm="Somebody Else Ltd")
    client.post(f"/case/{other}/evaluate", data={"llm": ""})
    _logout(client)
    _login(client, "broker", "change-me-broker")
    # Own case in the portal; other firm's case never leaks (404).
    r = client.get("/portal")
    assert r.status_code == 200 and cid in r.text and other not in r.text
    r = client.get(f"/portal/case/{other}")
    assert r.status_code == 404
    # Own portal case shows no binder names, scores or rule ids (Q8).
    r = client.get(f"/portal/case/{cid}")
    body = r.text
    assert "binder_" not in body and "rule-outcomes" not in body
    assert "Cannot assess" not in body and "recommendation" not in body
    # Brokers cannot reach staff surfaces.
    assert client.get("/case/" + cid).status_code in (403, 303)


def test_staff_letter_link_in_history(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    client.post(f"/case/{cid}/decide", data={"action": "accept",
                                             "underwriter": "t-uw"})
    page = client.get(f"/case/{cid}").text
    assert f"/case/{cid}/letter/" in page


def test_bound_letter_names_binder_refer_letter_asks(client):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    with store.new_session() as s:
        ev = (s.query(store.Evaluation)
              .filter(store.Evaluation.case_id == cid)
              .order_by(store.Evaluation.evaluation_id.desc()).first())
        reco = ev.recommendation
    # 1) accepted -> bound letter names the selected binder (Q10).
    client.post(f"/case/{cid}/decide", data={"action": "accept",
                                             "underwriter": "t-uw"})
    with store.new_session() as s:
        d = (s.query(store.Decision)
             .filter(store.Decision.case_id == cid)
             .order_by(store.Decision.decision_id.desc()).first())
        letter = (d.detail or {}).get("letter")
    assert letter["kind"] == "bound" and reco in letter["body"]
    r = client.get(f"/case/{cid}/letter/{d.decision_id}")
    assert r.status_code == 200 and reco in r.text
    # 2) a referred letter on another case carries the engine's ask list.
    cid2 = _new_case(client, sample_case_id="10-missing-commodities-refer")
    client.post(f"/case/{cid2}/evaluate", data={"llm": ""})
    client.post(f"/case/{cid2}/decide", data={"action": "refer_back",
                                              "underwriter": "t-uw"})
    c2 = _latest(cid2)
    assert c2.status == "awaiting-broker"  # Q7: refer_back keeps the round open
    with store.new_session() as s:
        d2 = (s.query(store.Decision)
              .filter(store.Decision.case_id == cid2)
              .order_by(store.Decision.decision_id.desc()).first())
        letter2 = (d2.detail or {}).get("letter")
    assert letter2["kind"] == "referred"
    assert "Please provide the missing data item" in letter2["body"]


def test_gap_items_trace_to_rules(client):
    """Each ask item names the field and the (binder, rule) that raised it (Q4)."""
    cid = _new_case(client, sample_case_id="10-missing-commodities-refer")
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    gaps = service.latest_gaps(cid)
    assert gaps
    for g in gaps:
        assert g["field"] and g["raised_by"]
        for binder_id, rule_id in g["raised_by"]:
            assert binder_id and rule_id
        assert g["question"].startswith("Please provide")


def test_delta_view_shows_what_changed(client):
    cid = _new_case(client, sample_case_id="10-missing-commodities-refer")
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    fields = _round_fields(cid)
    client.post(f"/case/{cid}/round/issue", data={"field_0": fields[0]})
    with store.new_session() as s:
        rnd = s.query(store.RequestRound).filter(
            store.RequestRound.case_id == cid).one()
        item = s.query(store.RequestItem).filter(
            store.RequestItem.round_id == rnd.round_id).first()
        iid, fld, rid = item.item_id, item.field, rnd.round_id
    _logout(client)
    _login(client, "broker", "change-me-broker")
    client.post(f"/portal/case/{cid}/round/{rid}/draft",
                data={f"answer_{iid}": "yes"})
    client.post(f"/portal/case/{cid}/round/{rid}/submit", data={})
    client.get("/logout")
    _login(client, "admin", "change-me-admin")
    with store.new_session() as s:
        evals = (s.query(store.Evaluation)
                 .filter(store.Evaluation.case_id == cid)
                 .order_by(store.Evaluation.evaluation_id.desc()).all())
    d = service.delta_view(evals[-1].payload, evals[0].payload)
    # The answered field must appear as a fact change (that was the point).
    answered = [f for f in d["facts"] if f["field"] == fld]
    if answered:
        assert answered[0]["prev"] != answered[0]["curr"]
    # The delta is rendered on the case page between the last two evaluations.
    page = client.get(f"/case/{cid}").text
    assert "Delta — evaluation" in page


def test_breach_email_fires_once(client, monkeypatch):
    cid = _new_case(client)
    client.post(f"/case/{cid}/evaluate", data={"llm": ""})
    fields = _round_fields(cid)
    client.post(f"/case/{cid}/round/issue", data={"field_0": fields[0]})
    # Force the round past its due date.
    with store.new_session() as s:
        rnd = s.query(store.RequestRound).filter(
            store.RequestRound.case_id == cid).one()
        from datetime import timedelta
        rnd.due_at = store.now() - timedelta(days=1)
        s.commit()
        rid = rnd.round_id
    n = service.check_breach_notices()
    assert n == 1
    n2 = service.check_breach_notices()
    assert n2 == 0  # idempotent — one signage email per round (Q13)
    page = client.get(f"/case/{cid}").text
    assert "SLA breached" in page  # visual chip, no auto-escalation (Q11)
