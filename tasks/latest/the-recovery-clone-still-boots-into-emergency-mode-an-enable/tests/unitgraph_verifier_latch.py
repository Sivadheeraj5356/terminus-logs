"""Verifier latch: authenticate contracts/tools and invoke the public command."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

CONTRACT_DIR = Path("/app/systemd_boot_contracts")
PUBLIC_CMD = Path("/app/boot_recovery_console/reconcile_boot_graph.sh")
APP_BIN = Path("/app/rust_unitgraph_cells/reconcile_boot_graph")

EXPECTED_CONTRACT_HASHES = {
    "bootyard_custody_generation_protocol.md": "7d51302f70a954c80c1ca36a4f3f179cf87442d43d627400d9e8eedd35d07c2d",
    "cold_boot_evidence_receipt.md": "478e4aa303c6911b148def06148d44595ce646c561bf33533e6416f77d9dc0a5",
    "condition_assert_outcome_rules.md": "613ccb83d5a5c3c47fcdba18f3ae18c2a40ebad2cc120a994f3998a7ea16dad7",
    "dependency_job_transaction_code.md": "afb2b014771620869c71db0069479ef3f0e2f30a4c048436abb7aa960ffd90a1",
    "enablement_mask_preset_law.md": "dd92d3c3aae88e12e53b28d6aa088f9c0f55a8db29f9796ca3de37dc18feb909",
    "mount_automount_device_readiness.md": "ce55b8c5d44ef90d5dedb2060f82a2b7f0e0e81ce9ebac2436255c515c1508cb",
    "specifier_instance_escape_register.md": "42b24db1effee4679bf6831d152c5b6370abc1a3283be764c8ce1ffdd803aea9",
    "unit_fragment_precedence_contract.md": "b31297a4a75715966657403c21f6b9d1ae880c0a7a1437778a31c677c276aa83"
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def unitgraph_authenticate_session():
    assert PUBLIC_CMD.is_file(), "public command missing"
    assert APP_BIN.is_file(), "application binary missing"
    for name, digest in EXPECTED_CONTRACT_HASHES.items():
        path = CONTRACT_DIR / name
        assert path.is_file(), f"missing contract {name}"
        assert _sha256(path) == digest, f"contract hash mismatch {name}"
    yield


@pytest.fixture
def workdir(tmp_path):
    return tmp_path


def run_reconcile(yard: Path, order: Path, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        [str(PUBLIC_CMD), str(yard), str(order)],
        capture_output=True,
        text=True,
        env=e,
    )


def clone_tree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)
