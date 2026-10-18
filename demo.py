"""Full-project demo: sample submission through every gate.

Run:  python demo.py
Uses the stub extractor (no API key) so the run is deterministic.
Covers: extract -> derive -> completeness -> evaluate (all binders) -> rank
  -> review (auto-accept as demo underwriter) -> settle -> audit -> MI.
"""
# Command: resume interrupted graph.
from langgraph.types import Command
# build: construct graph.
from graph import build
# get_checkpointer, BASE: persistence helpers.
from persistence import get_checkpointer, BASE
# report: MI report.
from reports.mi import report

# SAMPLE_DOCS: demo submission documents.
SAMPLE_DOCS = [
    {"doc_id": "mail-001", "filename": "broker-email.eml",
     "text": "Broker: Acme Marine Ltd. TIV $6,500,000, 12-month All-Risk.",
      "structured_hint": {
          "total_insured_value": "$6,500,000", "broker_name": "Acme Marine Ltd.",
          "locations": [{"address": "12 Port Road", "sprinklered": True}],
          "commodities": [{"commodity_type": "STEEL"}],
          "coverage_sections": [{"limit": 2000000}],
          "valuation_basis": "CIF+10%", "coverage_type": "ALL_RISK",
          "requested_inception_date": "2030-06-01",
          "expiring_premium_disclosed": False,
          "insured_in_continental_us": True,
          "largest_single_claim_amount": 0, "total_claims_amount": 0}},
    {"doc_id": "sov-001", "filename": "sov.xlsx",
     "text": "SOV: 1 location, sprinklered, alarm present.",
     "structured_hint": {}},
]


# main: run the demo.
def main() -> None:
    import shutil
    # Wipe prior demo state.
    shutil.rmtree(BASE / "audit", ignore_errors=True)
    for f in ("ledger.json", ".checkpoints.sqlite"):
        (BASE / f).unlink(missing_ok=True)
        (BASE / "capacity" / f).unlink(missing_ok=True)
    print("=== 1. INTAKE: sample submission SUB-DEMO-001 (2 docs) ===")
    with get_checkpointer() as cp:
        g = build(checkpointer=cp)
        cfg = {"configurable": {"thread_id": "demo-1"}}
        g.invoke({"submission_reference": "SUB-DEMO-001", "documents": SAMPLE_DOCS}, cfg)
        snap = g.get_state(cfg)
        print("paused at:", snap.next)
        st = snap.values
        print("--- 2. EXTRACT: fields + confidence ---")
        for f, m in (st.get("extracted_meta") or {}).items():
            print(f"  {f}: value={st['extracted'].get(f)} conf={m.get('confidence')} src={m.get('source_document_id')}")
        print("--- 3. COMPLETENESS:", st.get("completeness"))
        print("--- 4+5. PER-BINDER EVALUATION ---")
        for r in st.get("binder_results", []):
            print(f"  {r['binder_id']}: {r['outcome']}",
                  r.get("reason", ""),
                  [(o["rule_id"], o["outcome"]) for o in r.get("rule_outcomes", [])])
        print("--- 6. RANK:", st.get("scores"), st.get("ranking"), "=>", st.get("recommendation"))
        print("--- 7. REVIEW: underwriter accepts ---")
        done = g.invoke(Command(resume={"action": "accept",
                                        "underwriter_id": "demo-underwriter"}), cfg)
        print("  decision:", done.get("decision"))
        print("--- 8. SETTLE:", done.get("settlement"))
        print("--- 9. AUDIT:", done.get("audit_id"))
    print("--- 10. MI (all local records) ---")
    mi = report()
    print("  volume:", mi["volume_mix"])
    print("  declines:", mi["decline_reasons"])
    print("  overrides:", mi["override_rate"])


if __name__ == "__main__":
    main()
