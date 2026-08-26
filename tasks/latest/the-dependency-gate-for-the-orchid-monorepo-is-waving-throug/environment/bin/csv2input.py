#!/usr/bin/env python3
"""Convert the ledger CSV fixtures and the OpenSSL hash report into the policy
input document consumed by the Rego bundle."""

import csv
import json

LEDGER = "/app/ledger/dependency_ledger.csv"
QUARANTINE = "/app/ledger/quarantine.csv"
META = "/app/ledger/meta.json"
HASH_REPORT = "/app/out/hash_report.json"
OUT = "/app/out/policy_input.json"


def parse_artifacts(cell):
    """Split the `path=digest;path=digest` ledger cell into artifact objects."""
    artifacts = []
    for pair in filter(None, cell.split(";")):
        path, _, digest = pair.partition("=")
        artifacts.append({"path": path, "digest": digest})
    return artifacts


def main():
    with open(META) as f:
        meta = json.load(f)
    with open(HASH_REPORT) as f:
        hash_report = json.load(f)

    dependencies = []
    with open(LEDGER, newline="") as f:
        for row in csv.DictReader(f):
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
                    "artifacts": parse_artifacts(row["artifacts"]),
                }
            )

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

    doc = {
        "generation": meta["generation"],
        "dependencies": dependencies,
        "hash_report": hash_report,
        "quarantine": quarantine,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"csv2input: wrote {len(dependencies)} dependencies to {OUT}")


if __name__ == "__main__":
    main()
