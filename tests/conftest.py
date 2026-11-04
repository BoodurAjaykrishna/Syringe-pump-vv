"""Shared fixtures and result collection for the verification run.

Every test declares the requirements it verifies with
`@pytest.mark.verifies("SRS-xxx")`. Results are written to
reports/results.json and turned into the traceability matrix by
tools/trace_report.py.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bench.test_bench import PumpTestBench
from firmware.pump_firmware import PumpConfig

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

DEFECTS = {
    # Seeded faults used to show that the test suite catches regressions.
    "late-occlusion": {"occlusion_debounce_ms": 1500},
}


def pytest_addoption(parser):
    parser.addoption("--inject-defect", choices=sorted(DEFECTS), default=None,
                     help="run against a firmware build with a seeded defect")


@pytest.fixture
def bench(request) -> PumpTestBench:
    overrides = DEFECTS.get(request.config.getoption("--inject-defect"), {})
    tb = PumpTestBench(PumpConfig(**overrides))
    yield tb
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", request.node.name)
    tb.bus.write_asc(REPORTS / "traces" / f"{name}.asc")


_results: list[dict] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        reqs = [r for m in item.iter_markers("verifies") for r in m.args]
        doc = (item.function.__doc__ or "").strip().splitlines()
        _results.append({
            "test": item.nodeid,
            "title": doc[0] if doc else item.name,
            "requirements": reqs,
            "outcome": report.outcome,
            "duration_s": round(report.duration, 3),
            "message": report.longreprtext.strip().splitlines()[-1] if report.failed else "",
        })


def pytest_sessionfinish(session, exitstatus):
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip() or "n/a"
    except OSError:
        commit = "n/a"
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "results.json").write_text(json.dumps({
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "commit": commit,
        "injected_defect": session.config.getoption("--inject-defect"),
        "results": _results,
    }, indent=2))
