"""Reset demo state: clear audit/ledger/checkpoints."""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def reset() -> None:
    # Remove audit dir.
    shutil.rmtree(ROOT / "audit", ignore_errors=True)
    # Remove ledger + checkpoints.
    for f in ("ledger.json", ".checkpoints.sqlite"):
        (ROOT / f).unlink(missing_ok=True)
        (ROOT / "capacity" / f).unlink(missing_ok=True)
        (ROOT / "ui" / f).unlink(missing_ok=True)
    print("demo state reset")


if __name__ == "__main__":
    reset()
