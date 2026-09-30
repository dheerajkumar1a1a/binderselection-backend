"""Data-driven vigorous suite: every samples/cases/*.json through the gate chain."""
import json
from pathlib import Path
import pytest
from nodes import completeness as comp
from nodes import capacity as cap
from nodes import appetite as app
from nodes import rank as rnk
from nodes.extract import stub_extract

CASES = Path(__file__).resolve().parent.parent / "samples" / "cases"


def load_cases():
    return sorted(CASES.glob("*.json"))


def run_case(case: dict) -> dict:
    state: dict = {"submission_reference": case["case_id"]}
    ext, meta = stub_extract(case["documents"])
    state["extracted"] = ext
    state["completeness"] = comp.check(state)["completeness"]
    if not state["completeness"]["can_evaluate"]:
        return {"halt": "completeness", "state": state}
    c = case.get("capacity", {})
    cap_out = cap.screen(state, c.get("line", 15_000_000.0),
                         c.get("written", 5_000_000.0), c.get("reserved", 0.0))
    state.update(capacity_snapshot=cap_out["capacity_snapshot"],
                 binder_outcome=cap_out["binder_outcome"])
    if state["binder_outcome"] != "eligible":
        return {"halt": "capacity", "state": state}
    state.update(app.evaluate(state))
    state.update(rnk.score(state))
    return {"halt": None, "state": state}


@pytest.mark.parametrize("path", load_cases(), ids=lambda p: p.stem)
def test_case(path):
    case = json.loads(path.read_text(encoding="utf-8"))
    res = run_case(case)
    exp = case["expected"]
    assert res["halt"] == exp["halt"], f"{case['case_id']}: halt mismatch"
    st = res["state"]
    if exp["halt"] == "completeness":
        assert st["completeness"]["missing"] == exp["missing"]
    elif exp["halt"] == "capacity":
        assert st["binder_outcome"].startswith("excluded")
        if "shortfall" in exp:
            tiv = st["extracted"]["total_insured_value"]
            avail = st["capacity_snapshot"]["available_capacity"]
            assert tiv - avail == exp["shortfall"]
    else:
        assert st["binder_outcome"] == case["binder_outcome"]
        assert st["recommendation"] == exp["recommendation"]
        got = {o["rule_id"]: o["outcome"] for o in st["rule_outcomes"]}
        for rid, outcome in exp.get("rules", {}).items():
            assert got.get(rid) == outcome, f"{case['case_id']}/{rid}"


def test_manifest_covers_all_cases():
    manifest = json.loads((CASES.parent / "manifest.json").read_text(encoding="utf-8"))
    listed = {c["file"] for c in manifest["cases"]}
    on_disk = {p.name for p in load_cases()}
    assert listed == on_disk
