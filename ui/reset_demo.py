"""Reset demo state: seed demo ledger from capacity.json, clear demo audit/UI artifacts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
caps = json.loads((ROOT / "rules" / "capacity.json").read_text())["binders"]
ledger = {"binders": {}}
for bid, c in caps.items():
    ledger["binders"][bid] = {
        "authorised_line": c["authorised_line"],
        "written_to_date": c["written_to_date"],
        "reservations": {}, "processed_binds": []}
(ROOT / "ui" / "demo-ledger.json").write_text(json.dumps(ledger, indent=2))
for f in ["ui/last-run.json", "ui/dbg_decide.py", "ui/dbg_http.py"]:
    (ROOT / f).unlink(missing_ok=True)
audit = ROOT / "audit" / "decisions.jsonl"
if audit.exists():
    lines = [ln for ln in audit.read_text().splitlines()
             if ln.strip() and "UI-" not in ln and "demo-underwriter" not in ln]
    audit.write_text(("\n".join(lines) + "\n") if lines else "")
print("demo ledger seeded:", {k: v["authorised_line"] for k, v in ledger["binders"].items()})
