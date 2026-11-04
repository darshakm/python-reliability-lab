from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from reliability_lab.demo import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_demo(*arguments: str) -> dict[str, object]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "reliability_lab.demo", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    result: dict[str, object] = json.loads(completed.stdout)
    return result


def test_concurrency_experiment_reports_capacity_boundary() -> None:
    result = run_demo(
        "concurrency",
        "--orders",
        "8",
        "--workers",
        "8",
        "--upstream-capacity",
        "2",
        "--latency",
        "0",
    )

    assert result["successful"] == 8
    peak = result["peak_dependency_concurrency"]
    assert isinstance(peak, int)
    assert peak <= 2


def test_outage_experiment_reports_retry_recovery() -> None:
    result = run_demo("outage", "--failures", "2", "--retries", "2")

    assert result["physical_attempts"] == 3
    assert result["outcome"] == "recovered"


@pytest.mark.parametrize(("mode", "calls"), [("on", 1), ("off", 8)])
def test_cache_stampede_experiment_compares_single_flight(
    mode: str, calls: int
) -> None:
    result = run_demo(
        "cache-stampede",
        "--callers",
        "8",
        "--single-flight",
        mode,
        "--latency",
        "0",
    )

    assert result["dependency_calls"] == calls
    assert result["all_callers_received_same_value"] is True


def test_recovery_experiment_traces_open_and_close() -> None:
    result = run_demo("recovery", "--threshold", "2")

    assert result["transitions"] == [
        "closed",
        "open",
        "rejected_while_open",
        "closed",
    ]


def test_demo_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="--workers must be at least 1"):
        main(["concurrency", "--workers", "0"])
