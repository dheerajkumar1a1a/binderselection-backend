"""Capacity console: maker-checker over versioned authorised lines (ADR-0002).

Covers the routes the rules console already had analogues for — propose,
four-eyes approve, diff, dry-run, revert, effective dating — plus the two
failures the browser pass found: the ledger must read the approved version,
and the proposals table must render its rows (an Alpine x-data scope bug
previously hid every row while looking like a styling problem).
"""
import json
import os
import tempfile
from pathlib import Path

# prod.store reads DATABASE_URL at import time.
_TMP = tempfile.mkdtemp(prefix="cap_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_TMP, "prod.sqlite3")).replace("\\", "/")

import pytest
from fastapi.testclient import TestClient

from prod import store, web
from prod.web import app as prod_app

from capacity import ledger as ledger_mod
from capacity import store as capstore
from prod import capacity_console as cc
from nodes import multibind
from nodes import capacity as cap


def _isolate(tmp_path, monkeypatch):
    """Point versions, proposals and the ledger at a throwaway directory."""
    versions = tmp_path / "versions"
    proposals = tmp_path / "proposals"
    versions.mkdir()
    monkeypatch.setattr(capstore, "VERSIONS_DIR", versions)
    monkeypatch.setattr(capstore, "PROPOSALS_DIR", proposals)
    monkeypatch.setattr(cc, "VERSIONS_DIR", str(versions))
    monkeypatch.setattr(cc, "PROPOSALS_DIR", str(proposals))
    monkeypatch.setattr(ledger_mod, "LEDGER_PATH", tmp_path / "ledger.json")
    return versions, proposals


@pytest.fixture()
def env(tmp_path, monkeypatch):
    store.init_db()
    versions, proposals = _isolate(tmp_path, monkeypatch)
    return {"versions": versions, "proposals": proposals, "tmp": tmp_path}


def _login(username: str) -> TestClient:
    c = TestClient(prod_app, follow_redirects=True)
    r = c.post("/login", data={"username": username,
                               "password": f"change-me-{username}"})
    assert r.status_code == 200
    return c


@pytest.fixture()
def admin(env):
    return _login("admin")


@pytest.fixture()
def uw(env):
    return _login("uw")


def _propose(client, binder_id="binder_C", line="25000000",
             effective_from="2026-01-01", summary="test uplift") -> str:
    r = client.post(f"/admin/capacity/propose/{binder_id}",
                    data={"authorised_line": line,
                          "effective_from": effective_from,
                          "summary": summary})
    assert r.status_code == 200
    assert "/admin/capacity/proposal/" in str(r.url)
    return str(r.url).rstrip("/").split("/")[-1]


# --- rendering ---------------------------------------------------------------

def test_capacity_page_lists_binders_and_seeds_versions(admin, env):
    r = admin.get("/admin/capacity")
    assert r.status_code == 200
    # Ledger is sourced from versioned lines, so every registry binder appears.
    for bid in ("binder_A", "binder_B", "binder_C", "binder_D", "binder_E"):
        assert bid in r.text
    assert "Live ledger" in r.text and "Binders" in r.text
    # v1 seeded from rules/capacity.json, effective-dated from binders.json.
    seeded = json.loads((env["versions"] / "binder_C_v1.json").read_text())
    assert seeded["authorised_line"] == 12_000_000.0
    assert seeded["effective_from"] == "2026-01-01"
    # Written/reserved are ledger facts, never authored into a version document.
    assert "written_to_date" not in seeded and "reserved" not in seeded


def test_proposals_table_rows_are_in_scope(admin, env):
    """Regression: x-data was scoped to the filter input, so x-show on rows
    raised 'search is not defined' and every row stayed hidden."""
    _propose(admin)
    html = admin.get("/admin/capacity").text
    marker = html.index('x-data="{search:')
    # The scope must open before the table, not inside the input only.
    assert marker < html.index("<tr x-show=")
    assert "P-" in html and "open →" in html


def test_proposal_page_blocks_self_approval_ui(admin, env):
    pid = _propose(admin)
    r = admin.get(f"/admin/capacity/proposal/{pid}")
    assert r.status_code == 200
    assert "You authored this proposal" in r.text
    assert "Approve (four-eyes)" not in r.text


# --- four-eyes lifecycle -----------------------------------------------------

def test_approve_writes_next_version_with_provenance(admin, uw, env):
    pid = _propose(admin)
    # Admin authored it, so admin cannot approve.
    assert admin.post(f"/admin/capacity/proposal/{pid}/approve").status_code == 400
    r = uw.post(f"/admin/capacity/proposal/{pid}/approve")
    assert r.status_code == 200 and "approved" in r.text

    doc = json.loads((env["versions"] / "binder_C_v2.json").read_text())
    assert doc["authorised_line"] == 25_000_000.0
    assert doc["version"] == 2 and doc["supersedes"] == 1
    assert doc["author"] == "admin" and doc["approver"] == "uw"

    # Second approval of the same proposal must not mint v3.
    assert uw.post(f"/admin/capacity/proposal/{pid}/approve").status_code == 400
    assert not (env["versions"] / "binder_C_v3.json").exists()


def test_unknown_proposal_and_binder_are_404(admin, env):
    assert admin.get("/admin/capacity/proposal/P-nope").status_code == 404
    assert admin.get("/admin/capacity/binder/binder_ZZ").status_code == 404


def test_engine_reads_the_approved_version(admin, uw, env):
    """The point of the ADR: approval must move eligibility, not just the desk."""
    before = multibind.capacity_for("binder_C")["authorised_line"]
    assert before == 12_000_000.0

    pid = _propose(admin, line="50000000")
    uw.post(f"/admin/capacity/proposal/{pid}/approve")

    after = multibind.capacity_for("binder_C")["authorised_line"]
    assert after == 50_000_000.0

    # 20m TIV was a shortfall at 12m; at 50m the binder accepts it.
    screened = cap.screen({"extracted": {"total_insured_value": 20_000_000}},
                          after, 0.0, 0.0)
    assert screened["binder_outcome"] == "eligible"


def test_future_effective_date_does_not_apply_yet(admin, uw, env):
    pid = _propose(admin, line="99000000", effective_from="2099-01-01")
    uw.post(f"/admin/capacity/proposal/{pid}/approve")
    # Approved and stored, but not in force: the engine keeps the old line.
    assert (env["versions"] / "binder_C_v2.json").exists()
    assert multibind.capacity_for("binder_C")["authorised_line"] == 12_000_000.0
    # And the history marks it future rather than in force.
    html = admin.get("/admin/capacity/binder/binder_C").text
    assert "future" in html


def test_revert_prefills_previous_line(admin, uw, env):
    pid = _propose(admin, line="30000000")
    uw.post(f"/admin/capacity/proposal/{pid}/approve")
    r = admin.get("/admin/capacity/propose/binder_C?rollback=1")
    assert r.status_code == 200
    assert "Reverting to v1" in r.text
    assert 'value="12000000.0"' in r.text


# --- diff and dry-run --------------------------------------------------------

def test_diff_shows_delta_and_field_change(admin, uw, env):
    pid = _propose(admin, line="25000000")
    uw.post(f"/admin/capacity/proposal/{pid}/approve")
    r = admin.get("/admin/capacity/binder/binder_C/diff?v1=1&v2=2")
    assert r.status_code == 200
    assert "+13,000,000" in r.text
    assert "+108.3%" in r.text
    assert "authorised_line" in r.text


def test_diff_needs_two_versions(admin, env):
    assert admin.get("/admin/capacity/binder/binder_C/diff").status_code == 400


def test_dry_run_defaults_to_all_sample_cases(admin, env):
    r = admin.post("/admin/capacity/dryrun/binder_C",
                   data={"authorised_line": "25000000", "case_ids": ""})
    assert r.status_code == 200
    out = json.loads(r.text.replace("<pre>", "").replace("</pre>", ""))
    assert out["total"] >= 29
    assert out["current_line"] == 12_000_000.0
    assert out["proposed_line"] == 25_000_000.0
    # Raising 12m -> 25m rescues the 20m TIV shortfall case.
    flips = {d["case"]: d for d in out["details"]}
    assert "04-capacity-shortfall" in flips
    assert flips["04-capacity-shortfall"]["after"] == "eligible"


def test_dry_run_rejects_non_numeric(admin, env):
    r = admin.post("/admin/capacity/dryrun/binder_C",
                   data={"authorised_line": "abc", "case_ids": ""})
    assert r.status_code == 400


# --- validation --------------------------------------------------------------

@pytest.mark.parametrize("bad", ["-1", "abc"])
def test_propose_rejects_invalid_line(admin, env, bad):
    r = admin.post("/admin/capacity/propose/binder_C",
                   data={"authorised_line": bad,
                         "effective_from": "2026-01-01", "summary": ""})
    assert r.status_code == 400


def test_empty_line_rejected_before_the_handler(admin, env):
    # Required form field: FastAPI refuses it with 422 without reaching us.
    r = admin.post("/admin/capacity/propose/binder_C",
                   data={"authorised_line": "",
                         "effective_from": "2026-01-01", "summary": ""})
    assert r.status_code in (400, 422)
    assert not list(env["proposals"].glob("*.json"))


def test_legacy_ledger_line_is_invisible_on_read(tmp_path, monkeypatch):
    """A pre-ADR ledger file still holds authorised_line; load() must drop it
    so no caller can read a second source of truth."""
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"binders": {"binder_A": {
        "authorised_line": 15_000_000.0, "written_to_date": 5_000_000.0,
        "reservations": {}, "processed_binds": []}}}))
    monkeypatch.setattr(ledger_mod, "LEDGER_PATH", path)
    loaded = ledger_mod.load()
    assert "authorised_line" not in loaded["binders"]["binder_A"]
    assert loaded["binders"]["binder_A"]["written_to_date"] == 5_000_000.0


def test_approve_without_prior_page_load_supersedes_seed(admin, uw, env):
    """Regression: approval on an unseeded binder wrote v1 and replaced the
    baseline instead of superseding it. Nothing here GETs the console first."""
    pid = _propose(admin)
    uw.post(f"/admin/capacity/proposal/{pid}/approve")
    doc = json.loads((env["versions"] / "binder_C_v2.json").read_text())
    assert doc["version"] == 2 and doc["supersedes"] == 1
    # The seeded baseline is still there, untouched.
    seeded = json.loads((env["versions"] / "binder_C_v1.json").read_text())
    assert seeded["authorised_line"] == 12_000_000.0


def test_non_staff_cannot_reach_capacity_console(env):
    c = TestClient(prod_app, follow_redirects=False)
    c.post("/login", data={"username": "broker", "password": "change-me-broker"})
    assert c.get("/admin/capacity").status_code in (303, 403)
