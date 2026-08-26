"""End-to-end checks for the StreamVault hardening task."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest


ROOT = Path("/workspace/streamvault")
PROGRAM = ROOT / "src" / "harden.mjs"
RUNBOOK = ROOT / "docs" / "operator-runbook.md"


def write_database(path: Path, *, alternate: bool = False, bad_port: bool = False) -> None:
    """Create a verifier-owned fleet database with the public task schema."""
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE sites (
          site_id TEXT PRIMARY KEY,
          admin_user TEXT NOT NULL,
          approved_bind TEXT NOT NULL,
          profile TEXT NOT NULL
        );
        CREATE TABLE cameras (
          camera_id TEXT PRIMARY KEY,
          site_id TEXT NOT NULL REFERENCES sites(site_id),
          enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
          approved_port INTEGER NOT NULL,
          media_fixture TEXT NOT NULL
        );
        CREATE TABLE retention_policies (
          profile TEXT PRIMARY KEY,
          min_days INTEGER NOT NULL,
          max_days INTEGER NOT NULL
        );
        CREATE TABLE service_networks (
          profile TEXT NOT NULL,
          service_name TEXT NOT NULL,
          allowed_cidr TEXT NOT NULL,
          PRIMARY KEY (profile, service_name, allowed_cidr)
        );
        CREATE TABLE exceptions (
          site_id TEXT NOT NULL REFERENCES sites(site_id),
          control_id TEXT NOT NULL,
          approved_value TEXT NOT NULL,
          rationale_id TEXT NOT NULL,
          expires_on TEXT NOT NULL,
          PRIMARY KEY (site_id, control_id, rationale_id)
        );
        CREATE TABLE exception_supersessions (
          site_id TEXT NOT NULL REFERENCES sites(site_id),
          control_id TEXT NOT NULL,
          predecessor_rationale_id TEXT NOT NULL,
          successor_rationale_id TEXT NOT NULL,
          PRIMARY KEY (site_id, control_id, predecessor_rationale_id, successor_rationale_id)
        );
        """
    )
    if alternate:
        connection.execute(
            "INSERT INTO sites VALUES (?, ?, ?, ?)",
            ("warehouse-93", "warehouse-operator", "127.0.0.2", "cold-storage"),
        )
        connection.execute(
            "INSERT INTO retention_policies VALUES (?, ?, ?)",
            ("cold-storage", 7, 21),
        )
        connection.execute(
            "INSERT INTO service_networks VALUES (?, ?, ?)",
            ("cold-storage", "camera-ingest", "192.0.2.0/24"),
        )
        connection.executemany(
            "INSERT INTO cameras VALUES (?, ?, ?, ?, ?)",
            [
                ("alpha", "warehouse-93", 1, 6100 if not bad_port else 80, "alpha.bin"),
                ("beta", "warehouse-93", 1, 5100, "beta.bin"),
                ("missing", "warehouse-93", 1, 7100, "missing.bin"),
                ("disabled", "warehouse-93", 0, 8100, "disabled.bin"),
                ("unsafe", "warehouse-93", 1, 9100, "../outside.bin"),
            ],
        )
        connection.execute(
            "INSERT INTO exceptions VALUES (?, ?, ?, ?, ?)",
            (
                "warehouse-93",
                "SV-SERVICE-07",
                '{"camera-ingest":"192.0.2.44"}',
                "EXC-PLANT7-INGEST",
                "2025-01-01",
            ),
        )
    else:
        schema = (ROOT / "fixtures" / "fleet.sql").read_text(encoding="utf-8")
        connection.close()
        path.unlink()
        connection = sqlite3.connect(path)
        connection.executescript(schema)
    connection.commit()
    connection.close()


def make_input(base: Path, *, alternate: bool = False) -> Path:
    """Create an input export whose values cannot be solved by the canonical fixture."""
    input_dir = base / "input"
    media = input_dir / "media"
    media.mkdir(parents=True)
    if alternate:
        (input_dir / "streamvault.yaml").write_text(
            """site_id: warehouse-93
security:
  admin_user: root
  admin_password: never-report-this-secret
  allow_anonymous: true
  tls_required: false
network:
  bind: 0.0.0.0
  ingest_ports: [9999]
recording:
  retention_days: 31
""",
            encoding="utf-8",
        )
        services = {
            "version": 9,
            "services": {
                "metrics": {"ports": ["9091:9091/tcp"], "bind": "::"},
                "camera-ingest": {"ports": ["9999:9999/tcp"], "bind": "::"},
                "admin-ui": {"ports": ["8443:8443/tcp"], "bind": "::"},
            },
        }
        (input_dir / "services.json").write_text(json.dumps(services), encoding="utf-8")
        (media / "alpha.bin").write_bytes(b"alpha-media")
        (media / "beta.bin").write_bytes(b"beta-media")
    else:
        shutil.copytree(ROOT / "input", input_dir, dirs_exist_ok=True)
    return input_dir


def run_hardener(
    tmp_path: Path,
    *,
    alternate: bool = False,
    bad_port: bool = False,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run the submitted hardener against an isolated verifier fixture."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "fleet.db"
    write_database(database, alternate=alternate, bad_port=bad_port)
    input_dir = make_input(tmp_path, alternate=alternate)
    output = tmp_path / "result"
    result = invoke_hardener(database, input_dir, output, env=env)
    return result, output, input_dir


def invoke_hardener(
    database: Path,
    input_dir: Path,
    output: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the hardener for a fully prepared verifier-owned case."""
    command = [
        "node",
        str(PROGRAM),
        "--fleet-db",
        str(database),
        "--runbook",
        str(RUNBOOK),
        "--input",
        str(input_dir),
        "--output",
        str(output),
    ]
    return subprocess.run(command, text=True, capture_output=True, env=env, timeout=30)


def load_json(path: Path) -> object:
    """Load JSON while requiring canonical indentation and one terminal newline."""
    text = path.read_text(encoding="utf-8")
    value = json.loads(text)
    assert text == json.dumps(value, indent=2, sort_keys=True) + "\n"
    return value


def digest_directory(path: Path) -> str:
    """Hash named output bytes in a stable order."""
    digest = hashlib.sha256()
    for file in sorted(path.iterdir(), key=lambda item: item.name):
        digest.update(file.name.encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
    return digest.hexdigest()


def test_canonical_fixture_is_hardened_and_deterministic(tmp_path: Path) -> None:
    """The supplied-style fixture must produce secure, byte-stable output."""
    result, output, _ = run_hardener(tmp_path)
    assert result.returncode == 0, result.stderr
    assert {item.name for item in output.iterdir()} == {
        "bundle-manifest.json",
        "streamvault.yaml",
        "services.json",
        "hardening-report.json",
    }
    config_text = output.joinpath("streamvault.yaml").read_text(encoding="utf-8")
    assert "factory-admin" not in config_text
    assert "admin_password:" not in config_text
    assert "admin_password_env: STREAMVAULT_ADMIN_PASSWORD" in config_text
    assert "admin_user: sv-plant7-admin" in config_text
    assert "allow_anonymous: false" in config_text
    assert "tls_required: true" in config_text
    assert "retention_days: 45" in config_text

    services = load_json(output / "services.json")
    assert services["services"]["camera-ingest"]["bind"] == "10.70.0.15"
    assert services["services"]["admin-ui"]["bind"] == "127.0.0.1"
    assert services["services"]["metrics"]["bind"] == "127.0.0.1"
    assert services["services"]["camera-ingest"]["ports"] == [
        "127.0.0.1:11554:11554/tcp",
        "127.0.0.1:12554:12554/tcp",
    ]

    report = load_json(output / "hardening-report.json")
    assert report["site_id"] == "plant-7"
    assert report["policy_date"] == "2025-12-31"
    assert all(change["evidence"] for change in report["changes"])
    assert all("factory-admin" not in json.dumps(change) for change in report["changes"])
    assert "ignored disabled camera retired" in report["warnings"]
    assert "ignored exception service not present in input: unknown-sidecar" in report["warnings"]
    retention = next(
        change for change in report["changes"] if change["control_id"] == "SV-RETENTION-08"
    )
    assert retention["after"] == 45
    assert any(item["source"] == "sqlite:retention_policies" for item in retention["evidence"])
    assert any(item["source"] == "sqlite:exceptions" for item in retention["evidence"])
    ingest_bind = next(
        change
        for change in report["changes"]
        if change["path"] == "services.camera-ingest.bind"
    )
    assert any(item["source"] == "sqlite:service_networks" for item in ingest_bind["evidence"])

    manifest = load_json(output / "bundle-manifest.json")
    assert manifest["algorithm"] == "sha256"
    assert [entry["path"] for entry in manifest["files"]] == [
        "hardening-report.json",
        "services.json",
        "streamvault.yaml",
    ]
    for entry in manifest["files"]:
        assert entry["sha256"] == hashlib.sha256(output.joinpath(entry["path"]).read_bytes()).hexdigest()
    root_material = "".join(
        f"{entry['sha256']}  {entry['path']}\n" for entry in manifest["files"]
    ).encode()
    assert manifest["root_sha256"] == hashlib.sha256(root_material).hexdigest()

    first_digest = digest_directory(output)
    rerun = subprocess.run(
        [
            "node",
            str(PROGRAM),
            "--fleet-db",
            str(tmp_path / "fleet.db"),
            "--runbook",
            str(RUNBOOK),
            "--input",
            str(tmp_path / "input"),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert rerun.returncode == 0, rerun.stderr
    assert digest_directory(output) == first_digest


def test_alternate_fleet_drives_values_and_filters_media(tmp_path: Path) -> None:
    """A verifier-owned site must control identity, ports, bindings, and warnings."""
    result, output, _ = run_hardener(tmp_path, alternate=True)
    assert result.returncode == 0, result.stderr
    config = subprocess.run(
        ["yq", "-o=json", ".", str(output / "streamvault.yaml")],
        text=True,
        capture_output=True,
        check=True,
    )
    parsed = json.loads(config.stdout)
    assert parsed["security"]["admin_user"] == "warehouse-operator"
    assert parsed["network"]["bind"] == "127.0.0.2"
    assert parsed["network"]["ingest_ports"] == [5100, 6100]
    assert parsed["recording"]["retention_days"] == 21

    services = load_json(output / "services.json")
    assert all(item["bind"] == "127.0.0.1" for item in services["services"].values())
    assert services["services"]["camera-ingest"]["ports"] == [
        "127.0.0.1:5100:5100/tcp",
        "127.0.0.1:6100:6100/tcp",
    ]

    report = load_json(output / "hardening-report.json")
    warnings = report["warnings"]
    assert "ignored disabled camera disabled" in warnings
    assert "ignored missing media fixture for camera missing: missing.bin" in warnings
    assert "ignored unsafe media fixture for camera unsafe: ../outside.bin" in warnings
    assert "ignored expired exception EXC-PLANT7-INGEST for SV-SERVICE-07" in warnings
    serialized = json.dumps(report)
    assert "never-report-this-secret" not in serialized
    assert "alpha.bin" in serialized and "beta.bin" in serialized


def test_invalid_approved_port_fails_without_partial_output(tmp_path: Path) -> None:
    """An eligible out-of-range registry port must fail before publishing files."""
    result, output, _ = run_hardener(tmp_path, alternate=True, bad_port=True)
    assert result.returncode != 0
    assert "port" in result.stderr.lower()
    assert not output.exists()


def test_unauthorized_exception_and_symlink_media_are_ignored(tmp_path: Path) -> None:
    """Authority comes from exact runbook headings and symlinks are not media evidence."""
    database = tmp_path / "fleet.db"
    write_database(database, alternate=True)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO cameras VALUES (?, ?, ?, ?, ?)",
        ("linked", "warehouse-93", 1, 6200, "linked.bin"),
    )
    connection.execute(
        "INSERT INTO exceptions VALUES (?, ?, ?, ?, ?)",
        ("warehouse-93", "SV-RETENTION-08", "365", "NO-SUCH-RATIONALE", "2026-12-31"),
    )
    connection.commit()
    connection.close()
    input_dir = make_input(tmp_path, alternate=True)
    (input_dir / "media" / "linked.bin").symlink_to(input_dir / "media" / "alpha.bin")
    output = tmp_path / "result"

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode == 0, result.stderr
    parsed = subprocess.run(
        ["yq", "-o=json", ".", str(output / "streamvault.yaml")],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(parsed.stdout)["recording"]["retention_days"] == 21
    report = load_json(output / "hardening-report.json")
    assert "ignored unsafe media fixture for camera linked: linked.bin" in report["warnings"]
    assert (
        "ignored unauthorized exception NO-SUCH-RATIONALE for SV-RETENTION-08"
        in report["warnings"]
    )


def test_ambiguous_exception_preserves_existing_output(tmp_path: Path) -> None:
    """Two authoritative current values fail without damaging a published bundle."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO exceptions VALUES (?, ?, ?, ?, ?)",
        (
            "plant-7",
            "SV-RETENTION-08",
            "60",
            "EXC-PLANT7-RETENTION-EXTENDED",
            "2026-12-31",
        ),
    )
    connection.commit()
    connection.close()
    input_dir = make_input(tmp_path)
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"keep-this-byte-for-byte")
    before = digest_directory(output)

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode != 0
    assert result.stderr.strip()
    assert digest_directory(output) == before


def test_exception_supersession_chain_selects_terminal_decision(tmp_path: Path) -> None:
    """A multi-hop decision history resolves to its unique current terminal."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.executemany(
        "INSERT INTO exceptions VALUES (?, ?, ?, ?, ?)",
        [
            ("plant-7", "SV-RETENTION-08", "60", "EXC-PLANT7-RETENTION-EXTENDED", "2026-12-31"),
            ("plant-7", "SV-RETENTION-08", "50", "EXC-PLANT7-RETENTION-FINAL", "2026-12-31"),
        ],
    )
    connection.executemany(
        "INSERT INTO exception_supersessions VALUES (?, ?, ?, ?)",
        [
            ("plant-7", "SV-RETENTION-08", "EXC-PLANT7-RETENTION", "EXC-PLANT7-RETENTION-EXTENDED"),
            ("plant-7", "SV-RETENTION-08", "EXC-PLANT7-RETENTION-EXTENDED", "EXC-PLANT7-RETENTION-FINAL"),
        ],
    )
    connection.commit()
    connection.close()

    output = tmp_path / "result"
    result = invoke_hardener(database, make_input(tmp_path), output)
    assert result.returncode == 0, result.stderr
    assert "retention_days: 50" in (output / "streamvault.yaml").read_text(encoding="utf-8")


def test_exception_supersession_branches_must_converge(tmp_path: Path) -> None:
    """Independent older decisions may converge on one authoritative terminal."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.executemany(
        "INSERT INTO exceptions VALUES (?, ?, ?, ?, ?)",
        [
            ("plant-7", "SV-RETENTION-08", "60", "EXC-PLANT7-RETENTION-EXTENDED", "2026-12-31"),
            ("plant-7", "SV-RETENTION-08", "75", "EXC-PLANT7-RETENTION-LEGAL", "2026-12-31"),
        ],
    )
    connection.executemany(
        "INSERT INTO exception_supersessions VALUES (?, ?, ?, ?)",
        [
            ("plant-7", "SV-RETENTION-08", "EXC-PLANT7-RETENTION", "EXC-PLANT7-RETENTION-LEGAL"),
            ("plant-7", "SV-RETENTION-08", "EXC-PLANT7-RETENTION-EXTENDED", "EXC-PLANT7-RETENTION-LEGAL"),
        ],
    )
    connection.commit()
    connection.close()

    output = tmp_path / "result"
    result = invoke_hardener(database, make_input(tmp_path), output)
    assert result.returncode == 0, result.stderr
    assert "retention_days: 75" in (output / "streamvault.yaml").read_text(encoding="utf-8")


def test_exception_supersession_cycle_is_atomic(tmp_path: Path) -> None:
    """A cyclic approval history is invalid and cannot replace a published bundle."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO exceptions VALUES (?, ?, ?, ?, ?)",
        ("plant-7", "SV-RETENTION-08", "60", "EXC-PLANT7-RETENTION-EXTENDED", "2026-12-31"),
    )
    connection.executemany(
        "INSERT INTO exception_supersessions VALUES (?, ?, ?, ?)",
        [
            ("plant-7", "SV-RETENTION-08", "EXC-PLANT7-RETENTION", "EXC-PLANT7-RETENTION-EXTENDED"),
            ("plant-7", "SV-RETENTION-08", "EXC-PLANT7-RETENTION-EXTENDED", "EXC-PLANT7-RETENTION"),
        ],
    )
    connection.commit()
    connection.close()
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"preserve-cycle-sentinel")
    before = digest_directory(output)

    result = invoke_hardener(database, make_input(tmp_path), output)
    assert result.returncode != 0
    assert "ambiguous" in result.stderr.lower()
    assert digest_directory(output) == before


def test_service_exception_outside_approved_cidr_is_atomic(tmp_path: Path) -> None:
    """A current exception cannot escape its profile's approved service networks."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE exceptions SET approved_value = ? WHERE control_id = ?",
        ('{"camera-ingest":"10.71.0.15"}', "SV-SERVICE-07"),
    )
    connection.commit()
    connection.close()
    input_dir = make_input(tmp_path)
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"stable-network-policy")
    before = digest_directory(output)

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode != 0
    assert result.stderr.strip()
    assert digest_directory(output) == before


def test_service_exception_accepts_any_approved_cidr(tmp_path: Path) -> None:
    """Multiple CIDR rows are alternatives and matching evidence is deterministic."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO service_networks VALUES (?, ?, ?)",
        ("factory-edge", "camera-ingest", "10.71.0.0/24"),
    )
    connection.execute(
        "UPDATE exceptions SET approved_value = ? WHERE control_id = ?",
        ('{"camera-ingest":"10.71.0.15"}', "SV-SERVICE-07"),
    )
    connection.commit()
    connection.close()
    input_dir = make_input(tmp_path)
    output = tmp_path / "result"

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode == 0, result.stderr
    services = load_json(output / "services.json")
    assert services["services"]["camera-ingest"]["bind"] == "10.71.0.15"
    report = load_json(output / "hardening-report.json")
    change = next(
        item for item in report["changes"] if item["path"] == "services.camera-ingest.bind"
    )
    cidrs = [
        item["value"]
        for item in change["evidence"]
        if item["source"] == "sqlite:service_networks"
    ]
    assert cidrs == ["10.71.0.0/24"]


def test_service_exception_honors_non_octet_cidr_prefix(tmp_path: Path) -> None:
    """CIDR matching uses prefix bits rather than textual octet comparison."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO service_networks VALUES (?, ?, ?)",
        ("factory-edge", "camera-ingest", "10.72.16.0/20"),
    )
    connection.execute(
        "UPDATE exceptions SET approved_value = ? WHERE control_id = ?",
        ('{"camera-ingest":"10.72.31.254"}', "SV-SERVICE-07"),
    )
    connection.commit()
    connection.close()
    input_dir = make_input(tmp_path)
    output = tmp_path / "result"

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode == 0, result.stderr
    services = load_json(output / "services.json")
    assert services["services"]["camera-ingest"]["bind"] == "10.72.31.254"
    report = load_json(output / "hardening-report.json")
    change = next(
        item for item in report["changes"] if item["path"] == "services.camera-ingest.bind"
    )
    assert {
        "source": "sqlite:service_networks",
        "key": "allowed_cidr",
        "value": "10.72.16.0/20",
    } in change["evidence"]


def test_malformed_service_cidr_preserves_existing_output(tmp_path: Path) -> None:
    """Every applicable registry CIDR must be valid, even beside a matching row."""
    database = tmp_path / "fleet.db"
    write_database(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO service_networks VALUES (?, ?, ?)",
        ("factory-edge", "camera-ingest", "10.70.0.0/99"),
    )
    connection.commit()
    connection.close()
    input_dir = make_input(tmp_path)
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"stable-malformed-cidr")
    before = digest_directory(output)

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode != 0
    assert result.stderr.strip()
    assert digest_directory(output) == before


@pytest.mark.parametrize("failure", ["unknown-site", "malformed-json", "invalid-policy"])
def test_registry_and_parse_failures_are_atomic(tmp_path: Path, failure: str) -> None:
    """Independent registry and parser failures preserve an existing published bundle."""
    database = tmp_path / "fleet.db"
    write_database(database, alternate=True)
    input_dir = make_input(tmp_path, alternate=True)
    if failure == "unknown-site":
        yaml_path = input_dir / "streamvault.yaml"
        yaml_path.write_text(
            yaml_path.read_text(encoding="utf-8").replace("warehouse-93", "unknown-site"),
            encoding="utf-8",
        )
    elif failure == "malformed-json":
        (input_dir / "services.json").write_text('{"services":', encoding="utf-8")
    else:
        connection = sqlite3.connect(database)
        connection.execute(
            "UPDATE retention_policies SET min_days = 90, max_days = 10 WHERE profile = ?",
            ("cold-storage",),
        )
        connection.commit()
        connection.close()
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"stable")
    before = digest_directory(output)

    result = invoke_hardener(database, input_dir, output)
    assert result.returncode != 0
    assert digest_directory(output) == before


def test_external_tool_failure_preserves_existing_output(tmp_path: Path) -> None:
    """A failed required administration tool cannot partially publish a bundle."""
    database = tmp_path / "fleet.db"
    write_database(database, alternate=True)
    input_dir = make_input(tmp_path, alternate=True)
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"stable")
    before = digest_directory(output)
    wrappers = tmp_path / "wrappers"
    wrappers.mkdir()
    failing_yq = wrappers / "yq"
    failing_yq.write_text("#!/usr/bin/env bash\nexit 42\n", encoding="utf-8")
    failing_yq.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{wrappers}:{env['PATH']}"

    result = invoke_hardener(database, input_dir, output, env=env)
    assert result.returncode != 0
    assert "yq" in result.stderr.lower()
    assert digest_directory(output) == before


def test_checksum_failure_preserves_existing_output(tmp_path: Path) -> None:
    """Manifest hashing is inside the same atomic publication boundary."""
    database = tmp_path / "fleet.db"
    write_database(database, alternate=True)
    input_dir = make_input(tmp_path, alternate=True)
    output = tmp_path / "result"
    output.mkdir()
    (output / "previous.bundle").write_bytes(b"stable-before-hash")
    before = digest_directory(output)
    wrappers = tmp_path / "wrappers"
    wrappers.mkdir()
    failing = wrappers / "sha256sum"
    failing.write_text("#!/usr/bin/env bash\nexit 47\n", encoding="utf-8")
    failing.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{wrappers}:{env['PATH']}"

    result = invoke_hardener(database, input_dir, output, env=env)
    assert result.returncode != 0
    assert "sha256sum" in result.stderr.lower()
    assert digest_directory(output) == before


def test_required_command_line_tools_are_invoked(tmp_path: Path) -> None:
    """The implementation must actually invoke sqlite3, jq, and yq."""
    wrappers = tmp_path / "wrappers"
    wrappers.mkdir()
    log = tmp_path / "tools.log"
    base_path = os.environ["PATH"]
    for tool in ("sqlite3", "jq", "yq", "sha256sum"):
        real = shutil.which(tool)
        assert real, f"{tool} missing from verifier image"
        wrapper = wrappers / tool
        wrapper.write_text(
            f"#!/usr/bin/env bash\nprintf '%s\\n' '{tool}' >> '{log}'\nexec '{real}' \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{wrappers}:{base_path}"
    result, _, _ = run_hardener(tmp_path / "case", alternate=True, env=env)
    assert result.returncode == 0, result.stderr
    invoked = log.read_text(encoding="utf-8").splitlines()
    assert invoked.count("sqlite3") >= 3
    assert invoked.count("jq") >= 2
    assert invoked.count("yq") >= 2
    assert invoked.count("sha256sum") >= 4


@pytest.mark.parametrize("missing", ["streamvault.yaml", "services.json"])
def test_missing_required_input_is_rejected(tmp_path: Path, missing: str) -> None:
    """Missing configuration inputs must fail without publishing a bundle."""
    database = tmp_path / "fleet.db"
    write_database(database)
    input_dir = make_input(tmp_path)
    (input_dir / missing).unlink()
    output = tmp_path / "result"
    result = subprocess.run(
        [
            "node",
            str(PROGRAM),
            "--fleet-db",
            str(database),
            "--runbook",
            str(RUNBOOK),
            "--input",
            str(input_dir),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert not output.exists()
