"""Emit one CTRF report for every verifier outcome."""

import json
import time

RESULTS = []
START_MS = [0]


def pytest_addoption(parser):
    """Register the CTRF destination used by the shell verifier."""
    parser.addoption("--ctrf", action="store", default=None)


def pytest_configure(config):
    """Record suite start time."""
    START_MS[0] = int(time.time() * 1000)


def pytest_runtest_logreport(report):
    """Record each executed behavioral case once."""
    if report.when == "call":
        status = (
            "skipped" if report.skipped else ("failed" if report.failed else "passed")
        )
        RESULTS.append(
            {
                "name": report.nodeid,
                "status": status,
                "duration": int(report.duration * 1000),
            }
        )


def pytest_sessionfinish(session):
    """Write a compact CTRF result without overwriting another phase."""
    destination = session.config.getoption("--ctrf")
    if not destination:
        return
    summary = {
        "tests": len(RESULTS),
        "passed": sum(item["status"] == "passed" for item in RESULTS),
        "failed": sum(item["status"] == "failed" for item in RESULTS),
        "pending": 0,
        "skipped": sum(item["status"] == "skipped" for item in RESULTS),
        "other": 0,
        "start": START_MS[0],
        "stop": int(time.time() * 1000),
    }
    with open(destination, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "results": {
                    "tool": {"name": "pytest"},
                    "summary": summary,
                    "tests": RESULTS,
                }
            },
            stream,
        )
