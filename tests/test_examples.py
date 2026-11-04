from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_example(name: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "examples" / name)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_order_model_example() -> None:
    assert run_example("order_model.py") == "ord_123: 149.99 USD (shipped)"


def test_resilient_read_example() -> None:
    assert run_example("resilient_read.py") == (
        "recovered=ord_123 attempts=2 cache_hit=True"
    )
