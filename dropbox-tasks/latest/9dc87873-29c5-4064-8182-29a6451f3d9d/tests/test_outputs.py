"""Exact verifier for the compromised mTLS credential-rotation schedule."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

import pytest


TASK_ROOT = Path(os.environ.get("TASK_FILE_DIR", "/app/task_file"))
TEST_ROOT = Path(__file__).resolve().parent
CASES = (
    ("credential_incident.txt", "credential_schedule.json", "2414ad794975c9add56c6f0781dd77a7679a73ebb2cd88e2bf4f77030bb4eda8"),
    ("credential_incident_b.txt", "credential_schedule_b.json", "4699a6764a951d7905d56ab420dba8c7820965a30c5615ad7c48781a82bccebd"),
    ("credential_incident_c.txt", "credential_schedule_c.json", "4f22b36cfa872e92568442631e2752a2db331a77b82884c7a3362e6a3ba70fd5"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def invoke(binary: Path, input_path: Path, output_path: Path) -> dict:
    subprocess.run(
        [str(binary), str(input_path), str(output_path)],
        check=True,
        timeout=600,
        cwd=TASK_ROOT,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def expected_schedules() -> dict[str, dict]:
    required_outputs = [TASK_ROOT / "output" / output_name for _, output_name, _ in CASES]
    if not all(path.is_file() for path in required_outputs):
        pytest.skip("required schedule outputs are missing")
    with tempfile.TemporaryDirectory(prefix="credential-reference-") as temp:
        binary = Path(temp) / f"reference-{secrets.token_hex(12)}"
        subprocess.run(
            ["g++", "-std=c++20", "-O2", str(TEST_ROOT / "reference.cpp"), "-o", str(binary)],
            check=True,
            timeout=60,
        )
        expected = {}
        for input_name, _, _ in CASES:
            input_path = TASK_ROOT / "scan_input" / input_name
            output_path = Path(temp) / f"{input_name}.json"
            expected[input_name] = invoke(binary, input_path, output_path)
        return expected


def wave_count(path: Path) -> int:
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields[:2] == ["PARAM", "wave_count"]:
            return int(fields[2])
    raise AssertionError("wave_count is missing")


def assert_shape(data: object, count: int) -> None:
    assert type(data) is dict
    assert set(data) == {
        "credential_exposure_units",
        "peak_dual_trust_mb",
        "peak_escrow_mb",
        "total_response_minutes",
        "waves",
    }
    for field in (
        "credential_exposure_units",
        "peak_dual_trust_mb",
        "peak_escrow_mb",
        "total_response_minutes",
    ):
        assert type(data[field]) is int
    assert type(data["waves"]) is list and len(data["waves"]) == count
    wave_keys = {
        "wave_index",
        "action_ids",
        "change_minutes",
        "audit_minutes",
        "active_dual_trust_service_ids",
        "remaining_compromised_service_ids",
        "awaiting_attestation_service_ids",
        "attested_service_ids",
    }
    list_fields = wave_keys - {"wave_index", "change_minutes", "audit_minutes"}
    for index, wave in enumerate(data["waves"], start=1):
        assert type(wave) is dict and set(wave) == wave_keys
        assert wave["wave_index"] == index
        assert type(wave["change_minutes"]) is int
        assert type(wave["audit_minutes"]) is int
        for field in list_fields:
            assert type(wave[field]) is list
            assert all(type(value) is str for value in wave[field])
            assert wave[field] == sorted(wave[field], key=lambda value: value.encode("ascii"))


@pytest.mark.parametrize("input_name,output_name,input_hash", CASES)
def test_input_is_unchanged(input_name: str, output_name: str, input_hash: str) -> None:
    del output_name
    input_path = TASK_ROOT / "scan_input" / input_name
    assert input_path.is_file()
    assert sha256_file(input_path) == input_hash


@pytest.mark.parametrize("input_name,output_name,input_hash", CASES)
def test_required_output_has_exact_schema(input_name: str, output_name: str, input_hash: str) -> None:
    del input_hash
    input_path = TASK_ROOT / "scan_input" / input_name
    output_path = TASK_ROOT / "output" / output_name
    assert output_path.is_file(), f"missing /app/task_file/output/{output_name}"
    assert_shape(json.loads(output_path.read_text(encoding="utf-8")), wave_count(input_path))


@pytest.mark.parametrize("input_name,output_name,input_hash", CASES)
def test_schedule_is_the_exact_optimum(
    expected_schedules: dict[str, dict], input_name: str, output_name: str, input_hash: str
) -> None:
    del input_hash
    output_path = TASK_ROOT / "output" / output_name
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    assert actual == expected_schedules[input_name]
