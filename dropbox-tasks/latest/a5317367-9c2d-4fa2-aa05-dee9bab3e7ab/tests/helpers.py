"""Verifier utilities — pipeline execution only, no agent imports."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEVICE_COUNT = 96
VLAN_CATALOG_COUNT = 180
TRUNK_LINK_COUNT = 140
POLICY_CATALOG_COUNT = 90
VALIDATION_SCOPE_COUNT = 48
IN_SCOPE_COUNT = 47

# Verifier-owned golden maps — independent of agent-editable inventory/catalogs.
EXPECTED_VLAN_IDS = frozenset(range(2001, 2181))
EXPECTED_VALIDATION_SCOPE: list[str] = [
    "acc-amw-sea-admin-03",
    "acc-amw-sea-admin-06",
    "acc-amw-sea-admin-09",
    "acc-apac-sin-guest-wing-02",
    "acc-apac-sin-guest-wing-04",
    "acc-apac-sin-guest-wing-06",
    "acc-apac-sin-hub-01",
    "acc-apac-sin-hub-03",
    "acc-apac-sin-hub-05",
    "acc-apac-sin-hub-07",
    "acc-apac-tyo-mfg-02",
    "acc-apac-tyo-mfg-04",
    "acc-apac-tyo-mfg-06",
    "acc-apac-tyo-office-01",
    "acc-apac-tyo-office-03",
    "acc-apac-tyo-office-05",
    "acc-emea-fra-lab-01",
    "acc-emea-fra-lab-04",
    "acc-emea-fra-lab-07",
    "acc-emea-fra-office-02",
    "acc-emea-fra-office-05",
    "acc-emea-fra-ot-yard-03",
    "acc-emea-fra-ot-yard-06",
    "acc-emea-lon-tower-a-07",
    "acc-hq-dal-bldg1-01",
    "acc-hq-dal-bldg2-02",
    "core-apac-sin-01",
    "core-apac-tyo-01",
    "core-emea-fra-01",
    "dist-amw-sea-main-01",
    "dist-apac-tyo-main-01",
    "dist-apac-tyo-main-02",
    "dist-emea-fra-main-01",
    "dist-emea-fra-main-02",
    "dist-emea-lon-main-02",
    "dist-hq-dal-main-01",
    "rtr-amw-sea-edge-01",
    "rtr-apac-sin-edge-01",
    "rtr-apac-sin-edge-02",
    "rtr-apac-tyo-edge-01",
    "rtr-apac-tyo-edge-02",
    "rtr-apac-tyo-edge-03",
    "rtr-apac-tyo-edge-04",
    "rtr-apac-tyo-edge-05",
    "rtr-emea-fra-edge-01",
    "rtr-emea-fra-edge-02",
    "rtr-emea-fra-edge-03",
    "rtr-hq-dal-edge-04",
]
EXPECTED_MIGRATION_STATE: dict[str, str] = {
    "acc-amw-sea-admin-03": "legacy",
    "acc-amw-sea-admin-06": "legacy",
    "acc-amw-sea-admin-09": "legacy",
    "acc-amw-sea-plant-a-01": "segmented",
    "acc-amw-sea-plant-a-04": "segmented",
    "acc-amw-sea-plant-a-07": "segmented",
    "acc-amw-sea-plant-a-10": "segmented",
    "acc-amw-sea-plant-b-02": "segmented",
    "acc-amw-sea-plant-b-05": "segmented",
    "acc-amw-sea-plant-b-08": "segmented",
    "acc-apac-sin-guest-wing-02": "partial",
    "acc-apac-sin-guest-wing-04": "partial",
    "acc-apac-sin-guest-wing-06": "partial",
    "acc-apac-sin-hub-01": "partial",
    "acc-apac-sin-hub-03": "partial",
    "acc-apac-sin-hub-05": "partial",
    "acc-apac-sin-hub-07": "partial",
    "acc-apac-tyo-mfg-02": "legacy",
    "acc-apac-tyo-mfg-04": "legacy",
    "acc-apac-tyo-mfg-06": "legacy",
    "acc-apac-tyo-office-01": "legacy",
    "acc-apac-tyo-office-03": "legacy",
    "acc-apac-tyo-office-05": "legacy",
    "acc-emea-fra-lab-01": "legacy",
    "acc-emea-fra-lab-04": "legacy",
    "acc-emea-fra-lab-07": "legacy",
    "acc-emea-fra-office-02": "legacy",
    "acc-emea-fra-office-05": "legacy",
    "acc-emea-fra-ot-yard-03": "legacy",
    "acc-emea-fra-ot-yard-06": "legacy",
    "acc-emea-lon-tower-a-01": "segmented",
    "acc-emea-lon-tower-a-03": "segmented",
    "acc-emea-lon-tower-a-05": "segmented",
    "acc-emea-lon-tower-a-07": "partial",
    "acc-emea-lon-tower-b-02": "segmented",
    "acc-emea-lon-tower-b-04": "segmented",
    "acc-emea-lon-tower-b-06": "segmented",
    "acc-emea-lon-tower-b-08": "segmented",
    "acc-hq-dal-bldg1-01": "partial",
    "acc-hq-dal-bldg1-05": "segmented",
    "acc-hq-dal-bldg1-09": "segmented",
    "acc-hq-dal-bldg1-13": "segmented",
    "acc-hq-dal-bldg2-02": "partial",
    "acc-hq-dal-bldg2-06": "segmented",
    "acc-hq-dal-bldg2-10": "segmented",
    "acc-hq-dal-bldg2-14": "segmented",
    "acc-hq-dal-bldg3-03": "segmented",
    "acc-hq-dal-bldg3-07": "segmented",
    "acc-hq-dal-bldg3-11": "segmented",
    "acc-hq-dal-dc-wing-04": "segmented",
    "acc-hq-dal-dc-wing-08": "segmented",
    "acc-hq-dal-dc-wing-12": "segmented",
    "core-amw-sea-01": "segmented",
    "core-apac-sin-01": "partial",
    "core-apac-tyo-01": "legacy",
    "core-emea-fra-01": "legacy",
    "core-emea-lon-01": "segmented",
    "core-hq-dal-01": "segmented",
    "dist-amw-sea-main-01": "partial",
    "dist-amw-sea-main-02": "segmented",
    "dist-apac-sin-main-01": "segmented",
    "dist-apac-sin-main-02": "segmented",
    "dist-apac-sin-main-03": "segmented",
    "dist-apac-tyo-main-01": "legacy",
    "dist-apac-tyo-main-02": "legacy",
    "dist-emea-fra-main-01": "legacy",
    "dist-emea-fra-main-02": "legacy",
    "dist-emea-lon-main-01": "segmented",
    "dist-emea-lon-main-02": "partial",
    "dist-hq-dal-main-01": "segmented",
    "dist-hq-dal-main-02": "segmented",
    "dist-hq-dal-main-03": "segmented",
    "rtr-amw-sea-edge-01": "partial",
    "rtr-amw-sea-edge-02": "segmented",
    "rtr-amw-sea-edge-03": "segmented",
    "rtr-apac-sin-edge-01": "partial",
    "rtr-apac-sin-edge-02": "partial",
    "rtr-apac-sin-edge-03": "segmented",
    "rtr-apac-sin-edge-04": "segmented",
    "rtr-apac-sin-edge-05": "segmented",
    "rtr-apac-tyo-edge-01": "legacy",
    "rtr-apac-tyo-edge-02": "legacy",
    "rtr-apac-tyo-edge-03": "legacy",
    "rtr-apac-tyo-edge-04": "legacy",
    "rtr-apac-tyo-edge-05": "legacy",
    "rtr-emea-fra-edge-01": "legacy",
    "rtr-emea-fra-edge-02": "legacy",
    "rtr-emea-fra-edge-03": "legacy",
    "rtr-emea-lon-edge-01": "segmented",
    "rtr-emea-lon-edge-02": "segmented",
    "rtr-emea-lon-edge-03": "segmented",
    "rtr-emea-lon-edge-04": "segmented",
    "rtr-hq-dal-edge-01": "segmented",
    "rtr-hq-dal-edge-02": "segmented",
    "rtr-hq-dal-edge-03": "segmented",
    "rtr-hq-dal-edge-04": "partial",
}

def _resolve_app() -> Path:
    if Path("/app/environment").is_dir():
        return Path("/app")
    here = Path(__file__).resolve()
    for parent in here.parents:
        env = parent / "environment"
        if env.is_dir() and (env / "inventory").is_dir():
            return parent
    raise RuntimeError("could not locate task app root")


APP = _resolve_app()
ENV = APP / "environment"
OUTPUT = APP / "output"
RUNNER = ENV / "scripts" / "run-netsegctl.sh"
CONTRACT = ENV / "schemas" / "pipeline" / "exports.yaml"


def clear_output() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def _stage_env() -> dict[str, str]:
    return {
        **dict(os.environ),
        "ENV_ROOT": str(ENV),
        "OUTPUT_ROOT": str(OUTPUT),
    }


def run_stage(stage: str, *, timeout: int = 300, reset: bool = True) -> subprocess.CompletedProcess[str]:
    if reset:
        clear_output()
    return subprocess.run(
        [str(RUNNER), stage],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=_stage_env(),
    )


def run_stage_sequence(*stages: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    clear_output()
    last: subprocess.CompletedProcess[str] | None = None
    for stage in stages:
        last = subprocess.run(
            [str(RUNNER), stage],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_stage_env(),
        )
        if last.returncode != 0:
            return last
    assert last is not None
    return last




def load_output(name: str) -> dict[str, Any]:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def assert_stage_ok(result: subprocess.CompletedProcess[str], stage: str) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"stage {stage} failed (rc={result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _canonical_lineage(lineage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lineage:
        return lineage
    copy = json.loads(json.dumps(lineage))
    for key in (
        "source_drift",
        "resolved_from",
        "depends_on",
        "spine",
        "unrendered_in_scope_validation",
        "regional_membership_drift",
    ):
        if key in copy and isinstance(copy[key], list):
            copy[key] = sorted(copy[key]) if key != "spine" and key != "depends_on" and key != "resolved_from" else list(copy[key])
    return copy


def canonical_evidence(doc: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(json.dumps(doc))
    copy["devices"] = sorted(copy["devices"], key=lambda row: row["hostname"])
    for row in copy["devices"]:
        row["source_sections_consulted"] = sorted(row["source_sections_consulted"])
        row["legacy_sources_consulted"] = sorted(row.get("legacy_sources_consulted", []))
        row["retired_vlan_families"] = sorted(row.get("retired_vlan_families", []))
        row["superseded_sections"] = sorted(row.get("superseded_sections", []))
        row["duplicate_vlans"] = sorted(row.get("duplicate_vlans", []))
    if "lineage" in copy:
        copy["lineage"] = _canonical_lineage(copy["lineage"])
    return copy


def canonical_vlan(doc: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(json.dumps(doc))
    copy["devices"] = sorted(copy["devices"], key=lambda row: row["hostname"])
    for row in copy["devices"]:
        row["violations"] = sorted(row.get("violations", []))
    if "lineage" in copy:
        copy["lineage"] = _canonical_lineage(copy["lineage"])
    return copy


def canonical_trunk(doc: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(json.dumps(doc))
    copy["devices"] = sorted(copy["devices"], key=lambda row: row["hostname"])
    for row in copy["devices"]:
        row["violations"] = sorted(row.get("violations", []))
    if "lineage" in copy:
        copy["lineage"] = _canonical_lineage(copy["lineage"])
    return copy


def canonical_acl(doc: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(json.dumps(doc))
    copy["devices"] = sorted(copy["devices"], key=lambda row: row["hostname"])
    for row in copy["devices"]:
        row["violations"] = sorted(row.get("violations", []))
    if "lineage" in copy:
        copy["lineage"] = _canonical_lineage(copy["lineage"])
    return copy


def read_config(rel: str) -> str:
    return (ENV / rel).read_text(encoding="utf-8")


def write_config(rel: str, content: str) -> None:
    path = ENV / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
