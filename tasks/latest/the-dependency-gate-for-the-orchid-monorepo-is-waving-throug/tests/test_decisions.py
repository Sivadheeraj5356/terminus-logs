"""The decisions report for the shipped ledger must match the in-force rules,
recomputed here from the raw fixtures rather than trusted from any golden."""

import csv
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ledger_ref

LEDGER = "/app/ledger/dependency_ledger.csv"
QUARANTINE = "/app/ledger/quarantine.csv"
META = "/app/ledger/meta.json"
MODELS_ROOT = "/app/models"
DECISIONS = "/app/out/decisions.json"


def _parse_artifacts(cell):
    """Split the `path=digest;path=digest` ledger cell into artifact objects."""
    artifacts = []
    for pair in filter(None, cell.split(";")):
        path, _, digest = pair.partition("=")
        artifacts.append({"path": path, "digest": digest})
    return artifacts


def _build_input():
    """Rebuild the policy-input document straight from the shipped fixtures."""
    with open(META) as f:
        meta = json.load(f)

    dependencies = []
    paths = set()
    with open(LEDGER, newline="") as f:
        for row in csv.DictReader(f):
            artifacts = _parse_artifacts(row["artifacts"])
            paths.update(a["path"] for a in artifacts)
            dependencies.append(
                {
                    "name": row["name"],
                    "ecosystem": row["ecosystem"],
                    "version": row["version"],
                    "license": row["license"],
                    "channel": row["channel"],
                    "provenance": row["provenance"],
                    "lock_generation": int(row["lock_generation"]),
                    "scope": row["scope"],
                    "origin": row["origin"],
                    "install_scripts": row["install_scripts"] == "true",
                    "artifacts": artifacts,
                }
            )

    hash_report = {}
    for path in sorted(paths):
        full = os.path.join(MODELS_ROOT, path)
        if os.path.isfile(full):
            with open(full, "rb") as f:
                hash_report[path] = hashlib.sha256(f.read()).hexdigest()

    quarantine = []
    with open(QUARANTINE, newline="") as f:
        for row in csv.DictReader(f):
            quarantine.append(
                {
                    "kind": row["kind"],
                    "ecosystem": row["ecosystem"],
                    "name": row["name"],
                    "digest": row["digest"],
                    "status": row["status"],
                    "clause": row["clause"],
                }
            )

    return {
        "generation": meta["generation"],
        "dependencies": dependencies,
        "hash_report": hash_report,
        "quarantine": quarantine,
    }


def _actual_report():
    """Load the decisions report the audit pipeline produced."""
    with open(DECISIONS) as f:
        return json.load(f)


def test_report_written_with_generation():
    """The audit writes /app/out/decisions.json carrying the ledger generation."""
    report = _actual_report()
    assert report["generation"] == _build_input()["generation"]


def test_every_ledger_row_has_one_decision():
    """The report covers each ledger dependency exactly once, in contract order."""
    report = _actual_report()
    expected = ledger_ref.expected_report(_build_input())
    expected_keys = [
        (d["ecosystem"], d["name"], d["version"]) for d in expected["decisions"]
    ]
    actual_keys = [
        (d["ecosystem"], d["name"], d["version"]) for d in report["decisions"]
    ]
    assert actual_keys == expected_keys


def test_decisions_match_in_force_rules():
    """Every decision, reason list, and annotation list matches the handbook
    rules recomputed from the fixtures."""
    report = _actual_report()
    expected = ledger_ref.expected_report(_build_input())
    mismatches = []
    expected_by_key = {
        (d["ecosystem"], d["name"], d["version"]): d for d in expected["decisions"]
    }
    for entry in report["decisions"]:
        key = (entry["ecosystem"], entry["name"], entry["version"])
        want = expected_by_key.get(key)
        if entry != want:
            mismatches.append((key, want, entry))
    assert not mismatches, f"{len(mismatches)} decisions diverge: {mismatches[:4]}"
