"""Emit one CTRF report per verifier run, covering pass and fail outcomes."""

import json
import time

_TESTS = []
_START = [0]


def pytest_addoption(parser):
    """Register the option naming the CTRF output path."""
    parser.addoption("--ctrf", action="store", default=None)


def pytest_configure(config):
    """Stamp the run start time."""
    _START[0] = int(time.time() * 1000)


def pytest_runtest_logreport(report):
    """Record each test's final status once, from its decisive phase."""
    if report.when == "call":
        status = (
            "skipped" if report.skipped else ("failed" if report.failed else "passed")
        )
        _TESTS.append(
            {
                "name": report.nodeid,
                "status": status,
                "duration": int(getattr(report, "duration", 0.0) * 1000),
            }
        )
    elif report.when == "setup" and (report.skipped or report.failed):
        _TESTS.append(
            {
                "name": report.nodeid,
                "status": "skipped" if report.skipped else "failed",
                "duration": 0,
            }
        )


def pytest_sessionfinish(session):
    """Write the CTRF document to the requested path, if any."""
    path = session.config.getoption("--ctrf")
    if not path:
        return
    summary = {
        "tests": len(_TESTS),
        "passed": sum(1 for t in _TESTS if t["status"] == "passed"),
        "failed": sum(1 for t in _TESTS if t["status"] == "failed"),
        "pending": 0,
        "skipped": sum(1 for t in _TESTS if t["status"] == "skipped"),
        "other": 0,
        "start": _START[0],
        "stop": int(time.time() * 1000),
    }
    document = {
        "results": {
            "tool": {"name": "pytest"},
            "summary": summary,
            "tests": _TESTS,
        }
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)
