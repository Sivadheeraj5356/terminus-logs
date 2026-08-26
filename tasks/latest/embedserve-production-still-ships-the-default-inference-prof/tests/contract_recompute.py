#!/usr/bin/env python3
"""Independent harden report derivation from ops bundle, lockfile, and advisory DB."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ENV = Path("/app/environment")
PROFILES = ENV / "config/profiles.json"
PROFILE = "embedserve-default"
OPERATIVE_KEYS = (
    "model_sandbox_enabled",
    "allow_local_weight_files",
    "mmap_model_weights",
    "tokenizer_remote_code",
    "tokenizer_trust_remote_code",
)


def _digest16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _load_profile(name: str) -> dict:
    all_profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    return all_profiles[name]


def _section11_body(bundle_path: Path) -> str:
    body = bundle_path.read_text(encoding="utf-8")
    match = re.search(r"(## Section 11[\s\S]*?)(?=\n## )", body)
    if not match:
        raise RuntimeError("section 11 missing")
    return match.group(1)


def _operative_policy(section: str) -> dict[str, str]:
    row = re.search(
        r"A-2025-07[\s\S]*?ratification_status \*\*ratified\*\*; "
        r"model_sandbox_enabled \*\*(\w+)\*\*; "
        r"allow_local_weight_files \*\*(\w+)\*\*; "
        r"mmap_model_weights \*\*(\w+)\*\*; "
        r"tokenizer_remote_code \*\*(\w+)\*\*; "
        r"tokenizer_trust_remote_code \*\*(\w+)\*\*",
        section,
    )
    if not row:
        raise RuntimeError("ratified amendment row missing")
    keys = OPERATIVE_KEYS
    return {keys[i]: row.group(i + 1) for i in range(len(keys))}


def _cargo_audit(cfg: dict, inventory: dict[str, str]) -> list[dict]:
    lock_path = Path(cfg["lockfile_path"])
    sidecar_dir = lock_path.parent
    proc = subprocess.run(
        [
            "cargo",
            "audit",
            "--json",
            "--db",
            str(cfg["advisory_db_path"]),
            "--file",
            str(lock_path),
            "-n",
        ],
        cwd=str(sidecar_dir),
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1) or not proc.stdout.strip():
        raise RuntimeError(proc.stderr or proc.stdout or "cargo audit failed")
    payload = json.loads(proc.stdout)
    hits: list[dict] = []
    for item in payload.get("vulnerabilities", {}).get("list", []):
        advisory = item["advisory"]
        crate = advisory["package"]
        if crate not in inventory:
            continue
        version = inventory[crate]
        hits.append(
            {
                "crate_name": crate,
                "version": version,
                "advisory_id": advisory["id"],
                "severity": item.get("severity") or advisory.get("severity") or "medium",
                "package_spec": f"{crate} ({version})",
            }
        )
    return hits


def _inventory_components(db_path: Path, profile: str, role: str) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT crate_name, version
            FROM cargo_components
            WHERE profile_id = ? AND component_role = ?
            """,
            (profile, role),
        )
        return {name: version for name, version in cur.fetchall()}
    finally:
        conn.close()


def build_report(profile: str = PROFILE) -> dict:
    cfg = _load_profile(profile)
    bundle = Path(cfg["ops_bundle_path"])
    lock_path = Path(cfg["lockfile_path"])
    db_path = Path(cfg["inventory_path"])

    section = _section11_body(bundle)
    policy = _operative_policy(section)
    ops_digest = _digest16(section.encode("utf-8"))
    lock_digest = _digest16(lock_path.read_bytes())

    inventory = _inventory_components(db_path, profile, cfg["sidecar_role"])
    audit_hits = _cargo_audit(cfg, inventory)

    disabled: list[dict] = []
    evidence: list[dict] = []
    for hit in audit_hits:
        crate = hit["crate_name"]
        if crate not in inventory:
            continue
        disabled.append(
            {
                "crate_name": crate,
                "version": inventory[crate],
                "advisory_id": hit["advisory_id"],
            }
        )
        evidence.append(hit)

    disabled.sort(key=lambda row: row["crate_name"])
    defaults = [
        {"setting_key": key, "value": policy[key]} for key in OPERATIVE_KEYS
    ]
    defaults.sort(key=lambda row: row["setting_key"])

    return {
        "api_version": cfg["api_version"],
        "profile": profile,
        "opened_db_basename": db_path.name,
        "ops_section": cfg["ops_section"],
        "ops_digest": ops_digest,
        "lock_digest": lock_digest,
        "disabled_components": disabled,
        "inference_defaults_applied": defaults,
        "advisory_evidence_count": len(evidence),
        "sql_evidence": {
            "inventory_path": str(db_path),
            "components_disabled": len(disabled),
            "defaults_changed": len(defaults),
        },
        "_evidence": evidence,
        "_run_stamp": _digest16(f"{ops_digest}:{lock_digest}".encode("utf-8")),
    }


def deterministic_timestamp(run_stamp: str) -> str:
    offset = int(run_stamp[:8], 16) % 86_400
    base = datetime(2025, 7, 1, tzinfo=UTC)
    return base.replace(second=offset % 60, minute=(offset // 60) % 60).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else PROFILE
    print(json.dumps(build_report(name), indent=2))
