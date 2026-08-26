from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


VISIBLE_DIR = Path("/app/evidence")
VISIBLE_POLICY = VISIBLE_DIR / "extraction.policy"
VISIBLE_MANIFEST = VISIBLE_DIR / "layers.manifest"
VISIBLE_REPORT = Path("/app/output/extraction-security.json")
SOURCE = Path("/app/layer_gate.c")
DELIVERED_EXECUTABLE = Path("/app/layer-gate")
GATE = Path("/tmp/oci-layer-gate-candidate")
EXPECTED_VISIBLE = Path("/tests/cases/visible.json")
CASES = Path("/tests/cases")
HASHES = Path("/tests/evidence.sha256")
RUNNER = Path("/tests/run_unprivileged.py")
SECTIONS = [
    "external_symlink_targets",
    "hardlink_escape_attempts",
    "hardlink_resolution_failures",
    "malformed_whiteout_attempts",
    "namespace_confusion_attempts",
    "path_escape_attempts",
    "privilege_escalation_entries",
    "protected_path_mutations",
    "security_summary",
    "shadowed_member_attacks",
    "symlink_pivot_attempts",
    "whiteout_scope_abuses",
]
HIDDEN_CASES = sorted(path for path in CASES.glob("hidden-*") if path.is_dir())
HIDDEN_CHECKS = ["canonical_shape", *SECTIONS]


def canonical_report(value: object) -> bytes:
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


def run_gate(policy: Path, manifest: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "/usr/local/bin/python3",
            str(RUNNER),
            str(GATE),
            str(policy),
            str(manifest),
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_visible_evidence_is_frozen() -> None:
    expected = dict(
        line.split("  ", 1)[::-1]
        for line in HASHES.read_text().splitlines()
        if line.strip()
    )
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in VISIBLE_DIR.iterdir()
        if path.is_file()
    }
    assert actual == expected


def test_required_outputs_exist() -> None:
    assert SOURCE.is_file()
    assert DELIVERED_EXECUTABLE.is_file()
    assert os.access(DELIVERED_EXECUTABLE, os.X_OK)
    assert GATE.is_file()
    assert RUNNER.is_file()
    assert VISIBLE_REPORT.is_file()


def test_verifier_cases_are_private() -> None:
    assert Path("/tests").stat().st_mode & 0o777 == 0o700
    probe_source = Path("/tmp/layerfs-privacy-probe.c")
    probe = Path("/tmp/layerfs-privacy-probe")
    output = Path("/tmp/layerfs-privacy-probe.json")
    for path in (probe_source, probe, output):
        path.unlink(missing_ok=True)
    probe_source.write_text(
        '#include <stdio.h>\nint main(void){FILE *f=fopen("/tests/cases/visible.json","rb");'
        'if(f!=NULL){fclose(f);return 0;}return 1;}\n'
    )
    compile_result = subprocess.run(
        [
            "/usr/local/bin/python3",
            "/tests/compile_unprivileged.py",
            str(probe_source),
            str(probe),
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert compile_result.returncode == 0, compile_result.stderr
    result = subprocess.run(
        [
            "/usr/local/bin/python3",
            str(RUNNER),
            str(probe),
            str(VISIBLE_POLICY),
            str(VISIBLE_MANIFEST),
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert not output.exists()


def test_visible_report_is_canonical_encoding() -> None:
    raw = VISIBLE_REPORT.read_bytes()
    assert raw == canonical_report(json.loads(raw))


def test_visible_report_has_canonical_shape() -> None:
    raw = VISIBLE_REPORT.read_bytes()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    parsed = json.loads(raw)
    assert list(parsed) == SECTIONS


@pytest.mark.parametrize("section", SECTIONS)
def test_visible_section_matches_reference(section: str) -> None:
    actual = json.loads(VISIBLE_REPORT.read_text())
    expected = json.loads(EXPECTED_VISIBLE.read_text())
    assert actual[section] == expected[section]


@pytest.fixture(scope="session", params=HIDDEN_CASES, ids=lambda path: path.name)
def hidden_report(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[bytes, dict[str, object], dict[str, object]]:
    case: Path = request.param
    workspace = tmp_path_factory.mktemp(case.name)
    output = workspace / "report.json"
    result = run_gate(case / "extraction.policy", case / "layers.manifest", output)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    raw = output.read_bytes()
    expected = json.loads((CASES / f"{case.name}.json").read_bytes())
    return raw, json.loads(raw), expected


@pytest.mark.parametrize("check", HIDDEN_CHECKS)
def test_gate_generalises_to_held_out_layers(
    hidden_report: tuple[bytes, dict[str, object], dict[str, object]], check: str
) -> None:
    raw, actual, expected = hidden_report
    if check == "canonical_shape":
        assert raw == canonical_report(actual)
        assert list(actual) == SECTIONS
    else:
        assert actual[check] == expected[check]


def staged_bad_case(tmp_path: Path) -> Path:
    for source in VISIBLE_DIR.iterdir():
        if source.is_file():
            shutil.copyfile(source, tmp_path / source.name)
    return tmp_path / "layers.manifest"


def assert_clean_failure(policy: Path, manifest: Path, output: Path) -> None:
    output.write_bytes(b"stale report\n")
    result = run_gate(policy, manifest, output)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == ""
    assert not output.exists()


def test_bad_manifest_fails_cleanly(tmp_path: Path) -> None:
    manifest = staged_bad_case(tmp_path)
    manifest.write_bytes(b"LAYERS1\n")
    assert_clean_failure(tmp_path / "extraction.policy", manifest, tmp_path / "report.json")


def test_bad_policy_fails_cleanly(tmp_path: Path) -> None:
    manifest = staged_bad_case(tmp_path)
    policy = tmp_path / "extraction.policy"
    policy.write_bytes(b"OCI-POLICY-1\ntrusted_layers 99\nprotect etc/shadow\n")
    assert_clean_failure(policy, manifest, tmp_path / "report.json")


def test_layer_digest_mismatch_fails_cleanly(tmp_path: Path) -> None:
    manifest = staged_bad_case(tmp_path)
    layer = tmp_path / "layer-00.tar"
    data = bytearray(layer.read_bytes())
    data[600] ^= 1
    layer.write_bytes(data)
    assert_clean_failure(tmp_path / "extraction.policy", manifest, tmp_path / "report.json")


def test_bad_tar_checksum_fails_cleanly(tmp_path: Path) -> None:
    manifest = staged_bad_case(tmp_path)
    layer = tmp_path / "layer-00.tar"
    data = bytearray(layer.read_bytes())
    data[0] ^= 1
    layer.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    lines = manifest.read_text().splitlines()
    lines[1] = f"{digest} layer-00.tar"
    manifest.write_text("\n".join(lines) + "\n")
    assert_clean_failure(tmp_path / "extraction.policy", manifest, tmp_path / "report.json")


def test_truncated_tar_fails_cleanly(tmp_path: Path) -> None:
    manifest = staged_bad_case(tmp_path)
    layer = tmp_path / "layer-00.tar"
    data = layer.read_bytes()[:-512]
    layer.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    lines = manifest.read_text().splitlines()
    lines[1] = f"{digest} layer-00.tar"
    manifest.write_text("\n".join(lines) + "\n")
    assert_clean_failure(tmp_path / "extraction.policy", manifest, tmp_path / "report.json")
