"""Verifier tests for reconcile-dnssec-rollover-publication-journals.

Publisher sources are copied from /app/environment into /app during image build.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

EPOCH = 1784006400
DATA = Path("/data")
WORK = Path("/work")
OUT = Path("/output")
ANCHOR = DATA / "trust-anchors" / "example.test.anchor"
ALT_ORIGIN = "alt.example.test."
ALT_ANCHOR = DATA / "trust-anchors" / "alt.example.test.anchor"
HISTORY_NAME = "release-log.jsonl"


def _sha256(path: Path) -> str:
    proc = subprocess.run(
        ["sha256sum", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout.split()[0]


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def ensure_bind_limits() -> None:
    """Raise NOFILE and close leaked fds before BIND signing tools run."""
    subprocess.run(["bash", "/app/scripts/ensure-limits.sh"], check=True)


@pytest.fixture(scope="session", autouse=True)
def build_app() -> None:
    """Rebuild zonepub from the agent-editable sources before grading."""
    subprocess.run(["make", "-C", "/app", "build"], check=True)


@pytest.fixture(autouse=True)
def reset_workflows() -> None:
    """Reset writable workflow copies from immutable /data fixtures."""
    _run(["/app/scripts/reset-workflows.sh"])
    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.is_file():
            path.unlink()


def publish(scenario: str, out: Path = OUT) -> None:
    ws = WORK / scenario
    _run(
        [
            "/app/bin/zonepub",
            "publish",
            "--workspace",
            str(ws),
            "--output-dir",
            str(out),
            "--epoch",
            str(EPOCH),
        ]
    )


def verify_signed(path: Path, origin: str = "example.test.", anchor: Path = ANCHOR) -> None:
    _run(["dnssec-verify", "-o", origin, str(path), str(anchor)])


def soa_counter(signed: Path) -> int:
    import re

    text = signed.read_text()
    match = re.search(r"SOA\s+[^(]+\(\s*(\d+)", text, re.S)
    if match:
        return int(match.group(1))
    manifest = OUT / "publication-manifest.json"
    if manifest.exists():
        return int(json.loads(manifest.read_text())["serial"])
    raise AssertionError("SOA counter not found")


def history_lines(scenario: str) -> list[str]:
    path = WORK / scenario / HISTORY_NAME
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


def test_normal_repeat_byte_stable() -> None:
    """Unchanged inputs at the fixed epoch must be byte-identical across repeated publish."""
    publish("normal")
    verify_signed(OUT / "example.test.signed")
    first_zone = _sha256(OUT / "example.test.signed")
    first_index = _sha256(OUT / "publication-manifest.json")
    history_before = history_lines("normal")
    publish("normal")
    assert _sha256(OUT / "example.test.signed") == first_zone
    assert _sha256(OUT / "publication-manifest.json") == first_index
    assert history_lines("normal") == history_before


def test_interrupted_recovery() -> None:
    """Interrupted release resumes without resigning or duplicating accepted history."""
    publish("interrupted")
    verify_signed(OUT / "example.test.signed")
    first = _sha256(OUT / "example.test.signed")
    history_before = history_lines("interrupted")
    publish("interrupted")
    assert _sha256(OUT / "example.test.signed") == first
    assert len(history_lines("interrupted")) == len(history_before)


def test_rollback_snapshot_does_not_reactivate_retired_key() -> None:
    """Legacy snapshot import must not reactivate a KSK retired in accepted history."""
    ws = WORK / "rollback"
    publish("rollback")
    verify_signed(OUT / "example.test.signed")
    manifest = json.loads((OUT / "publication-manifest.json").read_text())
    statuses = {entry["key_tag"]: entry["status"] for entry in manifest["keys"]}
    snap = json.loads((ws / "operator-snapshot-v1.json").read_text())
    history = json.loads(history_lines("rollback")[-1])
    retired_tags = {
        entry["key_tag"]
        for entry in history.get("keys", [])
        if entry.get("status") in {"retired", "revoked"}
    }
    for key in snap["keys"]:
        if key["status"] == "active" and key["role"] == "KSK" and key["key_tag"] in retired_tags:
            assert statuses.get(key["key_tag"]) != "active"


def test_soa_counter_wraparound() -> None:
    """Effective SOA counter advances forward across the 32-bit boundary."""
    publish("wrap")
    verify_signed(OUT / "example.test.signed")
    counter = soa_counter(OUT / "example.test.signed")
    assert counter > 4294967290 or counter < 1000


def test_wrap_idempotent_after_accept() -> None:
    """Wraparound release stays byte-stable when inputs and epoch are unchanged."""
    publish("wrap")
    first = _sha256(OUT / "example.test.signed")
    history_before = history_lines("wrap")
    publish("wrap")
    assert _sha256(OUT / "example.test.signed") == first
    assert history_lines("wrap") == history_before


def test_release_index_fields_present() -> None:
    """Release index exposes schema_version and serial fields."""
    publish("normal")
    manifest = json.loads((OUT / "publication-manifest.json").read_text())
    assert manifest["schema_version"] == 2
    assert isinstance(manifest["serial"], int)


def test_inspect_release_index_command() -> None:
    """inspect-manifest remains compatible with supported release index JSON."""
    publish("normal")
    proc = _run(
        [
            "/app/bin/zonepub",
            "inspect-manifest",
            "--manifest",
            str(OUT / "publication-manifest.json"),
            "--format",
            "json",
        ]
    )
    payload = json.loads(proc.stdout)
    assert payload["origin"] == "example.test."


def test_fixture_immutability_checksums() -> None:
    """Immutable /data fixtures must not change during verifier runs."""
    before = {
        str(path.relative_to(DATA)): _sha256(path)
        for path in sorted(DATA.rglob("*"))
        if path.is_file()
    }
    publish("normal")
    publish("wrap")
    after = {
        str(path.relative_to(DATA)): _sha256(path)
        for path in sorted(DATA.rglob("*"))
        if path.is_file()
    }
    assert before == after


def test_rollback_history_monotonicity() -> None:
    """Rollback workflow must not shrink accepted release history."""
    publish("rollback")
    lines = history_lines("rollback")
    assert len(lines) >= 1


def test_invalid_legacy_snapshot_preserves_last_good_release() -> None:
    """Unsupported legacy snapshots must fail without changing the last good release."""
    publish("normal")
    good_zone = _sha256(OUT / "example.test.signed")
    good_manifest = _sha256(OUT / "publication-manifest.json")
    bad = WORK / "normal" / "unsupported-snapshot.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "origin": "example.test.",
                "serial": 1,
                "keys": [],
            }
        )
        + "\n"
    )
    proc = subprocess.run(
        [
            "/app/bin/zonepub",
            "import-snapshot",
            "--workspace",
            str(WORK / "normal"),
            "--snapshot",
            str(bad),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert _sha256(OUT / "example.test.signed") == good_zone
    assert _sha256(OUT / "publication-manifest.json") == good_manifest


def test_alternate_origin_inventory_publishes_valid_zone() -> None:
    """Publisher must sign arbitrary supported origins and DNSKEY inventories."""
    publish("altorigin")
    signed = OUT / "alt.example.test.signed"
    verify_signed(signed, ALT_ORIGIN, ALT_ANCHOR)
    manifest = json.loads((OUT / "publication-manifest.json").read_text())
    assert manifest["origin"] == ALT_ORIGIN
    assert manifest["schema_version"] == 2
    key_tags = {entry["key_tag"] for entry in manifest["keys"]}
    assert len(key_tags) >= 2
