"""Timings, model versions, evidence pack, supersession (BFR-MI-006, AUD-004/005/008)."""
from nodes.timing import timed
from persistence import evidence_pack
from reports.mi import stage_timing


def test_timed_records_duration():
    out = timed("s", lambda s: {"x": 1})({})
    assert out["x"] == 1 and out["stage_timings"]["s"] >= 0.0


def test_model_versions_recorded():
    from nodes.extract import extract
    assert extract({"documents": []})["model_versions"]["extraction"] == "stub-1"


def test_evidence_pack_contains_all_sections():
    rec = {"evaluation_id": "eval-1", "submission_reference": "S",
           "evaluated_at": "t",
           "extracted_meta": {"f": {"value": 1, "confidence": 0.9, "source_document_id": "d",
                                    "corrected_by": "u", "corrected_at": "t2", "pre_correction_value": 2}},
           "binder_results": [{"binder_id": "A", "outcome": "Accept", "ruleset_version": 2,
                               "rule_outcomes": [{"rule_id": "R", "outcome": "Pass", "value": 1}]}],
           "recommendation": "A", "scores": {"A": 7.0},
           "decision": {"action": "accept", "selected_binder": "A", "underwriter_id": "u", "decided_at": "t3"},
           "settlement": {"action": "reserved"},
           "model_versions": {"extraction": "stub-1"},
           "stage_timings": {"extract": 0.01}, "supersedes": "eval-0"}
    pack = evidence_pack(rec)
    for needle in ("eval-1", "corrected by u", "ruleset v2", "Supersedes", "eval-0", "reserved", "stub-1"):
        assert needle in pack, needle


def test_stage_timing_aggregates():
    recs = [{"stage_timings": {"extract": 0.1, "rank": 0.2}},
            {"stage_timings": {"extract": 0.3}},
            {}]
    assert stage_timing(recs) == {"mean_seconds": {"extract": 0.2, "rank": 0.2}, "n": 3}
    assert stage_timing([]) == {"gap": "no timed records yet"}


def test_audit_persists_links(tmp_path, monkeypatch):
    import persistence as P
    monkeypatch.setattr(P, "BASE", tmp_path)
    from persistence import write_audit
    out = write_audit({"submission_reference": "S", "supersedes": "eval-0",
                       "model_versions": {"extraction": "stub-1"}})
    import json
    rec = json.loads((tmp_path / "audit" / "decisions.jsonl").read_text().splitlines()[0])
    assert rec["supersedes"] == "eval-0"
    assert rec["model_versions"] == {"extraction": "stub-1"}
    assert out["audit_id"] == rec["evaluation_id"]
