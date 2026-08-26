"""Verifier for bastion SSH access-control security audit."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

CLI = ["node", "/app/bastion_cli/src/cli.mjs"]
PRISTINE_BUNDLE = Path("/app/staging/bundle.tar.gz")
WORK = Path("/tmp/bastion_test_work")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _canonical_manifest_payload(changes: list[dict]) -> str:
    ordered = sorted(changes, key=lambda item: item["path"])
    return json.dumps(ordered, separators=(",", ":"))


def _manifest_hash(changes: list[dict]) -> str:
    return hashlib.sha256(_canonical_manifest_payload(changes).encode("utf-8")).hexdigest()


def _wrong_full_manifest_hash(manifest: dict) -> str:
    """Desk trap: hash pretty-printed full manifest object."""
    pretty = json.dumps(manifest, indent=2, sort_keys=True)
    return hashlib.sha256(pretty.encode("utf-8")).hexdigest()


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [*CLI, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode not in (0, 3):
        raise AssertionError(proc.stderr + proc.stdout)
    return proc


def _fresh_staging(name: str = "default") -> Path:
    """Isolate staging trees; use distinct names when a test needs multiple concurrent trees."""
    base = WORK / name
    if base.exists():
        shutil.rmtree(base)
    staging = base / "staging"
    staging.mkdir(parents=True)
    shutil.copy2(PRISTINE_BUNDLE, staging / "bundle.tar.gz")
    return staging


def _reseed_redis() -> None:
    proc = subprocess.run(
        ["node", "/app/scripts/seed_redis.mjs"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def _sshd_conf(staging: Path) -> str:
    return (
        staging / "extracted/ssh/sshd_config.d/bastion.conf"
    ).read_text(encoding="utf-8")


def _repair_tenant(staging: Path, tenant: str, manifest_name: str = "fix.json") -> dict:
    manifest_path = staging / manifest_name
    _run(
        [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            tenant,
            "--manifest",
            str(manifest_path),
        ]
    )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _audit_tenant(staging: Path, tenant: str, report_name: str = "audit.json") -> dict:
    report_path = staging / report_name
    _run(
        [
            "audit",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            tenant,
            "--report",
            str(report_path),
        ],
        check=False,
    )
    return json.loads(report_path.read_text(encoding="utf-8"))


@pytest.fixture
def redis_registry() -> None:
    _reseed_redis()
    yield
    _reseed_redis()


@pytest.fixture(scope="module", autouse=True)
def bastion_stack() -> None:
    proc = subprocess.run(
        ["/app/scripts/bastion-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


class TestAudit:
    def test_audit_finds_expected_violation_kinds(self) -> None:
        """Drifted bundle yields ssh, mode, sshd, sudoers, and unauthorized sudoers violations."""
        staging = _fresh_staging()
        report_path = staging / "audit.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--report",
                str(report_path),
            ],
            check=False,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        kinds = {v["kind"] for v in report["violations"]}
        assert "ssh_key_mismatch" in kinds
        assert "mode_mismatch" in kinds
        assert "sshd_setting" in kinds
        assert "sudoers_missing" in kinds
        assert "sudoers_unauthorized" in kinds
        assert report["clean"] is False
        assert report["staging_root"].endswith("/extracted")
        assert report["tenant"] == "prod"
        assert report["violations"] == sorted(
            report["violations"],
            key=lambda item: (item["path"], item["kind"]),
        )

    def test_audit_reads_live_redis_ssh_key(self, redis_registry: None) -> None:
        """Audit compares staged keys against live Redis, not static fixture files."""
        live_key = "ssh-rsa LIVEAUDITKEY alice@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key],
            check=True,
        )
        staging = _fresh_staging()
        report_path = staging / "audit_live.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--report",
                str(report_path),
            ],
            check=False,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        alice = [
            v
            for v in report["violations"]
            if v["path"] == "homes/alice/.ssh/authorized_keys"
            and v["kind"] == "ssh_key_mismatch"
        ]
        assert alice
        assert alice[0]["expected"] == live_key


class TestRepair:
    def test_repair_then_audit_clean(self) -> None:
        """Repair removes drift and follow-up audit is clean."""
        staging = _fresh_staging()
        manifest_path = staging / "fix_manifest.json"
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(manifest_path),
            ]
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["noop"] is False
        assert manifest["changes"]
        assert manifest["staging_root"].endswith("/extracted")
        assert manifest["tenant"] == "prod"
        assert manifest["changes"] == sorted(
            manifest["changes"],
            key=lambda item: item["path"],
        )
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

        for change in manifest["changes"]:
            assert set(change) == {"path", "before_sha256", "after_sha256"}
            assert len(change["before_sha256"]) == 64
            assert len(change["after_sha256"]) == 64
            assert change["before_sha256"] != change["after_sha256"]
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

        report_path = staging / "audit_after.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["clean"] is True
        assert report["violations"] == []

    def test_second_repair_is_noop(self) -> None:
        """Second repair emits noop manifest with canonical manifest_sha256."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "prod",
        ]
        first = staging / "fix1.json"
        second = staging / "fix2.json"
        _run([*args, "--manifest", str(first)])
        _run([*args, "--manifest", str(second)])
        m1 = json.loads(first.read_text(encoding="utf-8"))
        m2 = json.loads(second.read_text(encoding="utf-8"))
        assert m2["noop"] is True
        assert m2["changes"] == []
        assert m1["manifest_sha256"] == _manifest_hash(m1["changes"])
        assert m2["manifest_sha256"] == _manifest_hash(m2["changes"])
        assert m1["manifest_sha256"] != m2["manifest_sha256"]

    def test_repair_applies_live_redis_ssh_key(self, redis_registry: None) -> None:
        """Repair restores authorized_keys from live Redis after registry mutation."""
        live_key = "ssh-rsa LIVEREPAIRKEY alice@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_tenant_sshd_overlay_applied(self) -> None:
        """Prod tenant overlay sets PermitRootLogin prohibit-password after repair."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "PermitRootLogin prohibit-password" in conf
        assert "MaxAuthTries 3" in conf

    def test_alice_authorized_keys_restored(self) -> None:
        """Repair restores Redis-backed alice SSH public key."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key.endswith("alice@corp")
        assert "WRONGKEY" not in key


class TestHeldOutStagingTenant:
    def test_staging_tenant_sshd_overlay_applied(self) -> None:
        """Held-out staging tenant deep-merge sets MaxAuthTries 4 and AllowUsers alice."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "staging",
                "--manifest",
                str(staging / "fix_staging.json"),
            ]
        )
        manifest = json.loads((staging / "fix_staging.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "staging"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "MaxAuthTries 4" in conf
        assert "AllowUsers alice" in conf
        assert "bob" not in conf.split("AllowUsers", 1)[-1]

    def test_staging_tenant_audit_clean_after_repair(self) -> None:
        """Repair with staging tenant then audit reports clean with matching staging_root."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "staging",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_staging.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "staging",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "staging"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True


class TestManifestDigestSpec:
    def test_empty_changes_digest_is_stable(self) -> None:
        """Noop repair manifest_sha256 matches compact JSON of empty sorted array."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "prod",
        ]
        _run([*args, "--manifest", str(staging / "fix1.json")])
        _run([*args, "--manifest", str(staging / "fix2.json")])
        m2 = json.loads((staging / "fix2.json").read_text(encoding="utf-8"))
        assert m2["changes"] == []
        assert m2["manifest_sha256"] == _manifest_hash([])
        assert m2["manifest_sha256"] == _sha256_text("[]")


class TestBehavioralIntegrity:
    """Observable invariants — no source-string or internal symbol requirements."""

    def test_audit_flags_rogue_deploy_as_unauthorized(self) -> None:
        """Pre-repair audit must report sudoers_unauthorized for rogue-deploy principal."""
        staging = _fresh_staging()
        report_path = staging / "audit_unauth.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--report",
                str(report_path),
            ],
            check=False,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        unauth = [
            v
            for v in report["violations"]
            if v["kind"] == "sudoers_unauthorized" and "rogue-deploy" in v["actual"]
        ]
        assert unauth
        assert report["clean"] is False

    def test_repair_preserves_registry_sudoers_line_order(self, redis_registry: None) -> None:
        """Repaired sudoers preserves bastion:sudoers_lines hash field order, not alpha sort."""
        subprocess.run(["redis-cli", "DEL", "bastion:sudoers_lines"], check=True)
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:sudoers_lines",
                "rule_a",
                "zebra-svc ALL=(ALL) NOPASSWD:/usr/bin/true",
                "rule_b",
                "alpha-svc ALL=(ALL) NOPASSWD:/usr/bin/id",
            ],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        lines = [
            line
            for line in (staging / "extracted/sudoers.d/bastion-users")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        assert lines[0].startswith("zebra-svc")
        assert lines[1].startswith("alpha-svc")

    def test_repair_prefers_live_ssh_keys_over_archive(self, redis_registry: None) -> None:
        """Repair writes authorized_keys from live bastion:ssh_keys not archive alias."""
        live_key = "ssh-rsa LIVEOVERARCHIVE alice@corp"
        archive_key = "ssh-rsa ARCHIVETRAP alice@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key],
            check=True,
        )
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys:archive", "alice", archive_key],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == live_key
        assert archive_key not in key

    def test_second_repair_is_idempotent_on_disk(self) -> None:
        """Noop second repair leaves extracted staging file digests unchanged."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "prod",
        ]
        _run([*args, "--manifest", str(staging / "fix1.json")])
        tracked = [
            staging / "extracted/homes/alice/.ssh/authorized_keys",
            staging / "extracted/sudoers.d/bastion-users",
            staging / "extracted/ssh/sshd_config.d/bastion.conf",
        ]
        before = {str(p): _sha256_file(p) for p in tracked}
        _run([*args, "--manifest", str(staging / "fix2.json")])
        after = {str(p): _sha256_file(p) for p in tracked}
        manifest = json.loads((staging / "fix2.json").read_text(encoding="utf-8"))
        assert manifest["noop"] is True
        assert before == after

    def test_runtime_cache_mutation_does_not_override_live_overlay(
        self,
        redis_registry: None,
    ) -> None:
        """Repair ignores freshly written stale cache values when live overlay differs."""
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:registry:cache:prod",
                "sshd_settings",
                '{"ssh/sshd_config.d/bastion.conf":{"PermitRootLogin":"yes","MaxAuthTries":"9"}}',
            ],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "PermitRootLogin prohibit-password" in conf
        assert "PermitRootLogin yes" not in conf
        assert "MaxAuthTries 3" in conf
        assert "MaxAuthTries 9" not in conf


class TestHeldOutEdgeTenant:
    def test_edge_tenant_sshd_overlay_applied(self) -> None:
        """Held-out edge tenant sets LoginGraceTime 90 and GatewayPorts no."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "edge",
                "--manifest",
                str(staging / "fix_edge.json"),
            ]
        )
        manifest = json.loads((staging / "fix_edge.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "edge"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "LoginGraceTime 90" in conf
        assert "GatewayPorts no" in conf

    def test_edge_ignores_stale_registry_cache(self) -> None:
        """Edge repair uses live overlay not stale cache LoginGraceTime 30."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "edge",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "LoginGraceTime 90" in conf
        assert "LoginGraceTime 30" not in conf
        assert "GatewayPorts yes" not in conf

    def test_edge_tenant_audit_clean_after_repair(self) -> None:
        """Edge repair then audit is clean."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "edge",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_edge.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "edge",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "edge"
        assert report["clean"] is True


class TestHeldOutVaultTenant:
    def test_vault_tenant_sshd_overlay_applied(self) -> None:
        """Held-out vault tenant sets MaxSessions 4 and AllowAgentForwarding no."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "vault",
                "--manifest",
                str(staging / "fix_vault.json"),
            ]
        )
        manifest = json.loads((staging / "fix_vault.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "vault"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "MaxSessions 4" in conf
        assert "AllowAgentForwarding no" in conf

    def test_vault_ignores_stale_registry_cache(self) -> None:
        """Vault repair uses live overlay not stale cache MaxSessions 10."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "vault",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "MaxSessions 4" in conf
        assert "MaxSessions 10" not in conf
        assert "AllowAgentForwarding yes" not in conf

    def test_vault_tenant_audit_clean_after_repair(self) -> None:
        """Vault repair then audit is clean."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "vault",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_vault.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "vault",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "vault"
        assert report["clean"] is True


class TestHeldOutCanaryTenant:
    def test_canary_tenant_sshd_overlay_applied(self) -> None:
        """Held-out canary tenant sets ClientAliveInterval 120 and X11Forwarding no."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "canary",
                "--manifest",
                str(staging / "fix_canary.json"),
            ]
        )
        manifest = json.loads((staging / "fix_canary.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "canary"
        assert manifest["staging_root"].endswith("/extracted")
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "ClientAliveInterval 120" in conf
        assert "X11Forwarding no" in conf

    def test_canary_tenant_audit_clean_after_repair(self) -> None:
        """Canary repair then audit is clean with schema fields populated."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "canary",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_canary.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "canary",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "canary"
        assert report["clean"] is True

    def test_canary_ignores_stale_registry_cache(self, redis_registry: None) -> None:
        """Repair uses live canary overlay not stale registry cache ClientAliveInterval 30."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "canary",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "ClientAliveInterval 120" in conf
        assert "ClientAliveInterval 30" not in conf


class TestHeldOutDrTenant:
    def test_dr_tenant_sshd_overlay_applied(self) -> None:
        """Held-out dr tenant sets MaxAuthTries 5 and AllowTcpForwarding no."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "dr",
                "--manifest",
                str(staging / "fix_dr.json"),
            ]
        )
        manifest = json.loads((staging / "fix_dr.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "dr"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "MaxAuthTries 5" in conf
        assert "AllowTcpForwarding no" in conf

    def test_dr_tenant_audit_clean_after_repair(self) -> None:
        """DR repair then audit is clean."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "dr",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_dr.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "dr",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "dr"
        assert report["clean"] is True

    def test_dr_ignores_stale_registry_cache(self) -> None:
        """Repair uses live dr overlay not stale cache AllowTcpForwarding yes."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "dr",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "AllowTcpForwarding no" in conf
        assert "AllowTcpForwarding yes" not in conf


class TestRegistryCache:
    def test_prod_repair_ignores_stale_cache_sshd(self) -> None:
        """Prod repair applies tenant overlay prohibit-password not cache PermitRootLogin yes."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "PermitRootLogin prohibit-password" in conf
        assert "PermitRootLogin yes" not in conf

    def test_staging_repair_ignores_stale_cache_allowusers(self) -> None:
        """Staging repair uses overlay AllowUsers alice not cache rogue-deploy suffix."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "staging",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "AllowUsers alice" in conf
        assert "rogue-deploy" not in conf


class TestSudoersAndModes:
    def test_repair_removes_rogue_deploy_and_restores_svc_deploy(self) -> None:
        """Repair removes unauthorized rogue-deploy and writes registry svc-deploy line."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        sudo = (staging / "extracted/sudoers.d/bastion-users").read_text(encoding="utf-8")
        assert "rogue-deploy" not in sudo
        assert "svc-deploy ALL=(ALL)" in sudo

    def test_bob_authorized_keys_restored(self) -> None:
        """Repair restores Redis-backed bob SSH public key."""
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "prod",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        key = (
            staging / "extracted/homes/bob/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key.endswith("bob@corp")

    def test_third_repair_still_noop(self) -> None:
        """Third consecutive repair remains noop with stable digest."""
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "prod",
        ]
        _run([*args, "--manifest", str(staging / "fix1.json")])
        _run([*args, "--manifest", str(staging / "fix2.json")])
        _run([*args, "--manifest", str(staging / "fix3.json")])
        m3 = json.loads((staging / "fix3.json").read_text(encoding="utf-8"))
        assert m3["noop"] is True
        assert m3["manifest_sha256"] == _manifest_hash([])


class TestDeepHardeningRoundB:
    """Round B cross-endpoint behavioral stress — no source-string checks."""

    def test_atlas_comet_sshd_overlays_do_not_cross(self, redis_registry: None) -> None:
        atlas = _fresh_staging("atlas_cross")
        comet = _fresh_staging("comet_cross")
        _run(
            [
                "repair",
                "--staging",
                str(atlas),
                "--bundle",
                str(atlas / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--manifest",
                str(atlas / "fix.json"),
            ]
        )
        _run(
            [
                "repair",
                "--staging",
                str(comet),
                "--bundle",
                str(comet / "bundle.tar.gz"),
                "--tenant",
                "comet",
                "--manifest",
                str(comet / "fix.json"),
            ]
        )
        atlas_conf = (atlas / "extracted/ssh/sshd_config.d/bastion.conf").read_text(
            encoding="utf-8",
        )
        comet_conf = (comet / "extracted/ssh/sshd_config.d/bastion.conf").read_text(
            encoding="utf-8",
        )
        assert "Compression yes" in atlas_conf
        assert "Banner /etc/issue.net" in comet_conf
        assert "Banner /etc/issue.net" not in atlas_conf
        assert "Compression yes" not in comet_conf

    def test_atlas_ignores_runtime_stale_cache(self, redis_registry: None) -> None:
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:registry:cache:atlas",
                "sshd_settings",
                '{"ssh/sshd_config.d/bastion.conf":{"Compression":"no","TCPKeepAlive":"no"}}',
            ],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Compression yes" in conf
        assert "TCPKeepAlive yes" in conf
        assert "Compression no" not in conf

    def test_comet_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "comet",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        manifest = json.loads((staging / "fix.json").read_text(encoding="utf-8"))
        assert manifest["changes"] == sorted(
            manifest["changes"],
            key=lambda item: item["path"],
        )
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    def test_comet_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "comet",
        ]
        _run([*args, "--manifest", str(staging / "fix1.json")])
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        _run([*args, "--manifest", str(staging / "fix2.json")])
        manifest = json.loads((staging / "fix2.json").read_text(encoding="utf-8"))
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest

    def test_atlas_audit_violations_sorted_before_repair(self) -> None:
        staging = _fresh_staging()
        report_path = staging / "audit_atlas.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--report",
                str(report_path),
            ],
            check=False,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["violations"] == sorted(
            report["violations"],
            key=lambda item: (item["path"], item["kind"]),
        )


class TestDeepHardeningRoundC:
    """Round C cross-endpoint behavioral stress — no source-string checks."""

    def test_orbit_pulse_cipher_overlays_do_not_cross(self, redis_registry: None) -> None:
        orbit = _fresh_staging("orbit_cross")
        pulse = _fresh_staging("pulse_cross")
        _run(
            [
                "repair",
                "--staging",
                str(orbit),
                "--bundle",
                str(orbit / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--manifest",
                str(orbit / "fix.json"),
            ]
        )
        _run(
            [
                "repair",
                "--staging",
                str(pulse),
                "--bundle",
                str(pulse / "bundle.tar.gz"),
                "--tenant",
                "pulse",
                "--manifest",
                str(pulse / "fix.json"),
            ]
        )
        orbit_conf = (orbit / "extracted/ssh/sshd_config.d/bastion.conf").read_text(
            encoding="utf-8",
        )
        pulse_conf = (pulse / "extracted/ssh/sshd_config.d/bastion.conf").read_text(
            encoding="utf-8",
        )
        assert "StrictModes yes" in orbit_conf
        assert "KexAlgorithms curve25519-sha256" in pulse_conf
        assert "KexAlgorithms curve25519-sha256" not in orbit_conf
        assert "StrictModes yes" not in pulse_conf

    def test_orbit_ignores_runtime_stale_cache(self, redis_registry: None) -> None:
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:registry:cache:orbit",
                "sshd_settings",
                '{"ssh/sshd_config.d/bastion.conf":{"StrictModes":"no","PubkeyAuthentication":"no"}}',
            ],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "StrictModes yes" in conf
        assert "PubkeyAuthentication yes" in conf
        assert "StrictModes no" not in conf

    def test_pulse_fifth_repair_still_noop(self) -> None:
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "pulse",
        ]
        for idx in range(1, 6):
            _run([*args, "--manifest", str(staging / f"fix{idx}.json")])
        manifest = json.loads((staging / "fix5.json").read_text(encoding="utf-8"))
        assert manifest["noop"] is True
        assert manifest["manifest_sha256"] == _manifest_hash([])

    def test_orbit_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        report_path = staging / "audit_orbit.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["clean"] is True
        assert report["tenant"] == "orbit"

    def test_pulse_live_ssh_keys_after_registry_mutation(self, redis_registry: None) -> None:
        live_alice = "ssh-rsa PULSEALICEKEY alice@corp"
        live_bob = "ssh-rsa PULSEBOBKEY bob@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_alice],
            check=True,
        )
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "bob", live_bob],
            check=True,
        )
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "pulse",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        alice = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        bob = (
            staging / "extracted/homes/bob/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert alice == live_alice
        assert bob == live_bob


class TestHeldOutAtlasTenant:
    def test_atlas_compression_overlay_applied(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--manifest",
                str(staging / "fix_atlas.json"),
            ]
        )
        manifest = json.loads((staging / "fix_atlas.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "atlas"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Compression yes" in conf
        assert "TCPKeepAlive yes" in conf

    def test_atlas_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Compression yes" in conf
        assert "Compression no" not in conf

    def test_atlas_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "atlas",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_atlas.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "atlas"
        assert report["clean"] is True


class TestHeldOutCometTenant:
    def test_comet_banner_overlay_applied(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "comet",
                "--manifest",
                str(staging / "fix_comet.json"),
            ]
        )
        manifest = json.loads((staging / "fix_comet.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "comet"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Banner /etc/issue.net" in conf
        assert "UseDNS no" in conf

    def test_comet_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "comet",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Banner /etc/issue.net" in conf
        assert "Banner /etc/motd" not in conf

    def test_comet_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "comet",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_comet.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "comet",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "comet"
        assert report["clean"] is True


class TestHeldOutOrbitTenant:
    def test_orbit_strictmodes_overlay_applied(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--manifest",
                str(staging / "fix_orbit.json"),
            ]
        )
        manifest = json.loads((staging / "fix_orbit.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "orbit"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "StrictModes yes" in conf
        assert "PubkeyAuthentication yes" in conf

    def test_orbit_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "StrictModes yes" in conf
        assert "StrictModes no" not in conf

    def test_orbit_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "orbit",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_orbit.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "orbit"
        assert report["clean"] is True


class TestHeldOutPulseTenant:
    def test_pulse_cipher_overlay_applied(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "pulse",
                "--manifest",
                str(staging / "fix_pulse.json"),
            ]
        )
        manifest = json.loads((staging / "fix_pulse.json").read_text(encoding="utf-8"))
        assert manifest["tenant"] == "pulse"
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "KexAlgorithms curve25519-sha256" in conf
        assert "Ciphers chacha20-poly1305@openssh.com" in conf

    def test_pulse_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "pulse",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "KexAlgorithms curve25519-sha256" in conf
        assert "KexAlgorithms diffie-hellman-group14-sha256" not in conf

    def test_pulse_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging()
        args = [
            "repair",
            "--staging",
            str(staging),
            "--bundle",
            str(staging / "bundle.tar.gz"),
            "--tenant",
            "pulse",
        ]
        _run([*args, "--manifest", str(staging / "fix.json")])
        report_path = staging / "audit_pulse.json"
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "pulse",
                "--report",
                str(report_path),
            ]
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["tenant"] == "pulse"
        assert report["clean"] is True


class TestDeskTrapBehavioral:
    """Desk docs exist but live CLI behavior must follow production contracts."""

    def test_atlas_policy_cache_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/atlas_policy_cache_desk.md")
        assert desk.is_file()
        assert "Compression no" in desk.read_text(encoding="utf-8")
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "atlas",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Compression yes" in conf

    def test_comet_staging_alias_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/comet_staging_alias_desk.md")
        assert desk.is_file()
        assert "COMET_TENANT=staging" in desk.read_text(encoding="utf-8")
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "comet",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "Banner /etc/issue.net" in conf
        assert "MaxAuthTries 4" not in conf

    def test_orbit_snapshot_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/orbit_snapshot_desk.md")
        assert desk.is_file()
        assert "registry_snapshot" in desk.read_text(encoding="utf-8")
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "orbit",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "StrictModes yes" in conf

    def test_pulse_global_first_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/pulse_global_first_desk.md")
        assert desk.is_file()
        assert "global_over_tenant" in desk.read_text(encoding="utf-8")
        staging = _fresh_staging()
        _run(
            [
                "repair",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                "pulse",
                "--manifest",
                str(staging / "fix.json"),
            ]
        )
        conf = (staging / "extracted/ssh/sshd_config.d/bastion.conf").read_text(encoding="utf-8")
        assert "KexAlgorithms curve25519-sha256" in conf
        allow_users = next(
            line for line in conf.splitlines() if line.startswith("AllowUsers ")
        )
        assert "alice" in allow_users
        assert "bob" not in allow_users.split("AllowUsers", 1)[-1]


class TestHeldOutNexusTenant:
    def test_nexus_clientalive_overlay_applied(self) -> None:
        """Held-out nexus tenant sets ClientAliveInterval 120 and X11Forwarding no."""
        staging = _fresh_staging("nexus_overlay")
        manifest = _repair_tenant(staging, "nexus", "fix_nexus.json")
        assert manifest["tenant"] == "nexus"
        conf = _sshd_conf(staging)
        assert "ClientAliveInterval 120" in conf
        assert "X11Forwarding no" in conf

    def test_nexus_ignores_seeded_registry_cache(self) -> None:
        """Nexus repair uses live overlay not stale cache ClientAliveInterval 30."""
        staging = _fresh_staging("nexus_cache")
        _repair_tenant(staging, "nexus")
        conf = _sshd_conf(staging)
        assert "ClientAliveInterval 120" in conf
        assert "ClientAliveInterval 30" not in conf
        assert "X11Forwarding yes" not in conf

    def test_nexus_tenant_audit_clean_after_repair(self) -> None:
        """Nexus repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("nexus_clean")
        _repair_tenant(staging, "nexus")
        report = _audit_tenant(staging, "nexus", "audit_nexus.json")
        assert report["tenant"] == "nexus"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True

    def test_nexus_manifest_digest_matches_sorted_changes(self) -> None:
        """Nexus repair manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("nexus_manifest")
        manifest = _repair_tenant(staging, "nexus")
        assert manifest["changes"] == sorted(
            manifest["changes"],
            key=lambda item: item["path"],
        )
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)


class TestHeldOutRiftTenant:
    def test_rift_maxsessions_overlay_applied(self) -> None:
        """Held-out rift tenant sets MaxSessions 4 and AllowTcpForwarding no."""
        staging = _fresh_staging("rift_overlay")
        manifest = _repair_tenant(staging, "rift", "fix_rift.json")
        assert manifest["tenant"] == "rift"
        conf = _sshd_conf(staging)
        assert "MaxSessions 4" in conf
        assert "AllowTcpForwarding no" in conf

    def test_rift_ignores_seeded_registry_cache(self) -> None:
        """Rift repair uses live overlay not stale cache MaxSessions 10."""
        staging = _fresh_staging("rift_cache")
        _repair_tenant(staging, "rift")
        conf = _sshd_conf(staging)
        assert "MaxSessions 4" in conf
        assert "MaxSessions 10" not in conf
        assert "AllowTcpForwarding yes" not in conf

    def test_rift_tenant_audit_clean_after_repair(self) -> None:
        """Rift repair then audit is clean."""
        staging = _fresh_staging("rift_clean")
        _repair_tenant(staging, "rift")
        report = _audit_tenant(staging, "rift", "audit_rift.json")
        assert report["clean"] is True
        assert report["tenant"] == "rift"

    def test_rift_second_repair_noop_preserves_files(self) -> None:
        """Second rift repair is noop and leaves sshd conf digest unchanged."""
        staging = _fresh_staging("rift_noop")
        _repair_tenant(staging, "rift", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "rift", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutPrismTenant:
    def test_prism_loglevel_overlay_applied(self) -> None:
        """Held-out prism tenant sets LogLevel VERBOSE and UsePAM yes."""
        staging = _fresh_staging("prism_overlay")
        manifest = _repair_tenant(staging, "prism", "fix_prism.json")
        assert manifest["tenant"] == "prism"
        conf = _sshd_conf(staging)
        assert "LogLevel VERBOSE" in conf
        assert "UsePAM yes" in conf

    def test_prism_ignores_seeded_registry_cache(self) -> None:
        """Prism repair uses live overlay not stale cache LogLevel QUIET."""
        staging = _fresh_staging("prism_cache")
        _repair_tenant(staging, "prism")
        conf = _sshd_conf(staging)
        assert "LogLevel VERBOSE" in conf
        assert "LogLevel QUIET" not in conf
        assert "UsePAM no" not in conf

    def test_prism_tenant_audit_clean_after_repair(self) -> None:
        """Prism repair then audit is clean."""
        staging = _fresh_staging("prism_clean")
        _repair_tenant(staging, "prism")
        report = _audit_tenant(staging, "prism", "audit_prism.json")
        assert report["clean"] is True

    def test_prism_audit_violations_sorted_before_repair(self) -> None:
        """Pre-repair prism audit violations are sorted by path then kind."""
        staging = _fresh_staging("prism_audit_sort")
        report = _audit_tenant(staging, "prism", "audit_prism_pre.json")
        assert report["clean"] is False
        assert report["violations"] == sorted(
            report["violations"],
            key=lambda item: (item["path"], item["kind"]),
        )


class TestHeldOutQuasarTenant:
    def test_quasar_permittty_overlay_applied(self) -> None:
        """Held-out quasar tenant sets PermitTTY no and PrintMotd no."""
        staging = _fresh_staging("quasar_overlay")
        manifest = _repair_tenant(staging, "quasar", "fix_quasar.json")
        assert manifest["tenant"] == "quasar"
        conf = _sshd_conf(staging)
        assert "PermitTTY no" in conf
        assert "PrintMotd no" in conf

    def test_quasar_ignores_seeded_registry_cache(self) -> None:
        """Quasar repair uses live overlay not stale cache PermitTTY yes."""
        staging = _fresh_staging("quasar_cache")
        _repair_tenant(staging, "quasar")
        conf = _sshd_conf(staging)
        assert "PermitTTY no" in conf
        assert "PermitTTY yes" not in conf
        assert "PrintMotd yes" not in conf

    def test_quasar_tenant_audit_clean_after_repair(self) -> None:
        """Quasar repair then audit is clean."""
        staging = _fresh_staging("quasar_clean")
        _repair_tenant(staging, "quasar")
        report = _audit_tenant(staging, "quasar", "audit_quasar.json")
        assert report["clean"] is True

    def test_quasar_fifth_repair_still_noop(self) -> None:
        """Fifth quasar repair remains noop with stable empty-array digest."""
        staging = _fresh_staging("quasar_fifth")
        for index in range(1, 5):
            _repair_tenant(staging, "quasar", f"fix{index}.json")
        manifest = _repair_tenant(staging, "quasar", "fix5.json")
        assert manifest["noop"] is True
        assert manifest["manifest_sha256"] == _manifest_hash([])


class TestDeepHardeningRoundD:
    def test_nexus_rift_sshd_overlays_do_not_cross(self, redis_registry: None) -> None:
        """Nexus and rift repairs on sibling trees keep distinct sshd directives."""
        nexus = _fresh_staging("nexus_cross")
        rift = _fresh_staging("rift_cross")
        _repair_tenant(nexus, "nexus")
        _repair_tenant(rift, "rift")
        nexus_conf = _sshd_conf(nexus)
        rift_conf = _sshd_conf(rift)
        assert "ClientAliveInterval 120" in nexus_conf
        assert "MaxSessions 4" in rift_conf
        assert "MaxSessions 4" not in nexus_conf
        assert "ClientAliveInterval 120" not in rift_conf

    def test_prism_quasar_sshd_overlays_do_not_cross(self, redis_registry: None) -> None:
        """Prism and quasar repairs on sibling trees keep distinct sshd directives."""
        prism = _fresh_staging("prism_cross")
        quasar = _fresh_staging("quasar_cross")
        _repair_tenant(prism, "prism")
        _repair_tenant(quasar, "quasar")
        prism_conf = _sshd_conf(prism)
        quasar_conf = _sshd_conf(quasar)
        assert "LogLevel VERBOSE" in prism_conf
        assert "PermitTTY no" in quasar_conf
        assert "PermitTTY no" not in prism_conf
        assert "LogLevel VERBOSE" not in quasar_conf

    def test_nexus_ignores_runtime_stale_cache(self, redis_registry: None) -> None:
        """Nexus repair ignores freshly written stale cache sshd_settings."""
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:registry:cache:nexus",
                "sshd_settings",
                '{"ssh/sshd_config.d/bastion.conf":{"ClientAliveInterval":"15","X11Forwarding":"yes"}}',
            ],
            check=True,
        )
        staging = _fresh_staging("nexus_runtime_cache")
        _repair_tenant(staging, "nexus")
        conf = _sshd_conf(staging)
        assert "ClientAliveInterval 120" in conf
        assert "ClientAliveInterval 15" not in conf

    def test_rift_live_ssh_keys_after_registry_mutation(self, redis_registry: None) -> None:
        """Rift repair restores bob authorized_keys from live Redis mutation."""
        live_key = "ssh-rsa RIFTLIVEKEY bob@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "bob", live_key],
            check=True,
        )
        staging = _fresh_staging("rift_live_key")
        _repair_tenant(staging, "rift")
        key = (
            staging / "extracted/homes/bob/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_prism_third_repair_still_noop(self) -> None:
        """Third prism repair remains noop."""
        staging = _fresh_staging("prism_third")
        _repair_tenant(staging, "prism", "fix1.json")
        _repair_tenant(staging, "prism", "fix2.json")
        manifest = _repair_tenant(staging, "prism", "fix3.json")
        assert manifest["noop"] is True

    def test_quasar_audit_clean_after_repair(self) -> None:
        """Quasar repair removes drift and follow-up audit is clean."""
        staging = _fresh_staging("quasar_audit_clean")
        _repair_tenant(staging, "quasar")
        report = _audit_tenant(staging, "quasar", "audit_quasar_after.json")
        assert report["clean"] is True
        assert report["violations"] == []


class TestDeepHardeningRoundE:
    def test_nexus_prod_sibling_staging_trees_independent(self) -> None:
        """Prod and nexus repairs on separate staging trees do not cross-contaminate."""
        prod = _fresh_staging("rounde_prod")
        nexus = _fresh_staging("rounde_nexus")
        _repair_tenant(prod, "prod")
        _repair_tenant(nexus, "nexus")
        prod_conf = _sshd_conf(prod)
        nexus_conf = _sshd_conf(nexus)
        assert "PermitRootLogin prohibit-password" in prod_conf
        assert "ClientAliveInterval 120" in nexus_conf
        assert "ClientAliveInterval 120" not in prod_conf

    def test_atlas_nexus_overlays_remain_distinct(self) -> None:
        """Atlas compression overlay does not bleed into nexus repair."""
        atlas = _fresh_staging("rounde_atlas")
        nexus = _fresh_staging("rounde_nexus2")
        _repair_tenant(atlas, "atlas")
        _repair_tenant(nexus, "nexus")
        assert "Compression yes" in _sshd_conf(atlas)
        assert "ClientAliveInterval 120" in _sshd_conf(nexus)
        assert "Compression yes" not in _sshd_conf(nexus)

    def test_comet_rift_overlays_remain_distinct(self) -> None:
        """Comet banner overlay does not bleed into rift repair."""
        comet = _fresh_staging("rounde_comet")
        rift = _fresh_staging("rounde_rift")
        _repair_tenant(comet, "comet")
        _repair_tenant(rift, "rift")
        assert "Banner /etc/issue.net" in _sshd_conf(comet)
        assert "MaxSessions 4" in _sshd_conf(rift)
        assert "Banner /etc/issue.net" not in _sshd_conf(rift)

    def test_orbit_prism_overlays_remain_distinct(self) -> None:
        """Orbit strict modes overlay does not bleed into prism repair."""
        orbit = _fresh_staging("rounde_orbit")
        prism = _fresh_staging("rounde_prism")
        _repair_tenant(orbit, "orbit")
        _repair_tenant(prism, "prism")
        assert "StrictModes yes" in _sshd_conf(orbit)
        assert "LogLevel VERBOSE" in _sshd_conf(prism)
        assert "StrictModes yes" not in _sshd_conf(prism)

    def test_pulse_quasar_overlays_remain_distinct(self) -> None:
        """Pulse cipher overlay does not bleed into quasar repair."""
        pulse = _fresh_staging("rounde_pulse")
        quasar = _fresh_staging("rounde_quasar")
        _repair_tenant(pulse, "pulse")
        _repair_tenant(quasar, "quasar")
        pulse_conf = _sshd_conf(pulse)
        quasar_conf = _sshd_conf(quasar)
        assert "KexAlgorithms curve25519-sha256" in pulse_conf
        assert "PermitTTY no" in quasar_conf
        assert "PermitTTY no" not in pulse_conf

    def test_edge_vault_nexus_triple_isolation(self) -> None:
        """Edge, vault, and nexus repairs keep distinct LoginGraceTime and ClientAlive."""
        edge = _fresh_staging("rounde_edge")
        vault = _fresh_staging("rounde_vault")
        nexus = _fresh_staging("rounde_nexus3")
        _repair_tenant(edge, "edge")
        _repair_tenant(vault, "vault")
        _repair_tenant(nexus, "nexus")
        assert "LoginGraceTime 90" in _sshd_conf(edge)
        assert "ClientAliveInterval 120" in _sshd_conf(nexus)
        vault_conf = _sshd_conf(vault)
        assert "LoginGraceTime 90" not in vault_conf or "ClientAliveInterval 120" not in vault_conf


class TestBehavioralIntegrityRound2:
    def test_mode_mismatch_audit_normalizes_octal(self) -> None:
        """Audit reports mode_mismatch using registry octal expectations."""
        staging = _fresh_staging("behavior_mode_audit")
        report = _audit_tenant(staging, "prod", "audit_modes.json")
        mode_violations = [v for v in report["violations"] if v["kind"] == "mode_mismatch"]
        assert mode_violations
        paths = {v["path"] for v in mode_violations}
        assert "homes/alice/.ssh" in paths or "homes/alice/.ssh/authorized_keys" in paths

    def test_repair_restores_alice_ssh_directory_mode(self) -> None:
        """Repair applies registry file_modes to alice .ssh directory."""
        staging = _fresh_staging("behavior_alice_mode")
        _repair_tenant(staging, "prod")
        mode = oct(
            (staging / "extracted/homes/alice/.ssh").stat().st_mode & 0o777
        )[2:]
        assert mode in {"700", "0700"}

    def test_nexus_change_digests_match_on_disk_bytes(self) -> None:
        """Every nexus manifest change after_sha256 matches repaired file bytes."""
        staging = _fresh_staging("behavior_nexus_digests")
        manifest = _repair_tenant(staging, "nexus")
        for change in manifest["changes"]:
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

    def test_rift_audit_staging_root_is_absolute(self) -> None:
        """Rift audit report staging_root is an absolute extracted path."""
        staging = _fresh_staging("behavior_rift_root")
        report = _audit_tenant(staging, "rift", "audit_rift_root.json")
        assert report["staging_root"].startswith("/")
        assert report["staging_root"].endswith("/extracted")

    def test_prism_unauthorized_still_flagged_pre_repair(self) -> None:
        """Prism pre-repair audit still reports sudoers_unauthorized for rogue-deploy."""
        staging = _fresh_staging("behavior_prism_unauth")
        report = _audit_tenant(staging, "prism", "audit_prism_unauth.json")
        unauth = [v for v in report["violations"] if v["kind"] == "sudoers_unauthorized"]
        assert unauth

    def test_quasar_repair_then_audit_violation_kinds_empty(self) -> None:
        """Quasar post-repair audit has no violations of any kind."""
        staging = _fresh_staging("behavior_quasar_empty")
        _repair_tenant(staging, "quasar")
        report = _audit_tenant(staging, "quasar", "audit_quasar_empty.json")
        assert report["violations"] == []


class TestCrossTenantIsolationRound2:
    def test_nexus_and_prod_manifests_use_distinct_tenants(self) -> None:
        """Nexus and prod manifests record their respective tenant ids."""
        nexus = _fresh_staging("iso_nexus")
        prod = _fresh_staging("iso_prod")
        nexus_manifest = _repair_tenant(nexus, "nexus", "fix_nexus.json")
        prod_manifest = _repair_tenant(prod, "prod", "fix_prod.json")
        assert nexus_manifest["tenant"] == "nexus"
        assert prod_manifest["tenant"] == "prod"
        assert nexus_manifest["manifest_sha256"] != prod_manifest["manifest_sha256"]

    def test_rift_and_staging_allowusers_differ(self) -> None:
        """Rift keeps bob in AllowUsers while staging tenant restricts to alice."""
        rift = _fresh_staging("iso_rift")
        staging_t = _fresh_staging("iso_staging")
        _repair_tenant(rift, "rift")
        _repair_tenant(staging_t, "staging")
        rift_conf = _sshd_conf(rift)
        staging_conf = _sshd_conf(staging_t)
        assert "bob" in rift_conf.split("AllowUsers", 1)[-1]
        assert "bob" not in staging_conf.split("AllowUsers", 1)[-1]

    def test_prism_and_canary_sshd_directives_differ(self) -> None:
        """Prism LogLevel VERBOSE does not appear in canary repair output."""
        prism = _fresh_staging("iso_prism")
        canary = _fresh_staging("iso_canary")
        _repair_tenant(prism, "prism")
        _repair_tenant(canary, "canary")
        assert "LogLevel VERBOSE" in _sshd_conf(prism)
        assert "LogLevel VERBOSE" not in _sshd_conf(canary)

    def test_quasar_and_dr_sshd_directives_differ(self) -> None:
        """Quasar PermitTTY no does not appear in dr repair output."""
        quasar = _fresh_staging("iso_quasar")
        dr = _fresh_staging("iso_dr")
        _repair_tenant(quasar, "quasar")
        _repair_tenant(dr, "dr")
        assert "PermitTTY no" in _sshd_conf(quasar)
        assert "PermitTTY no" not in _sshd_conf(dr)

    def test_nexus_and_vault_sequential_repairs_independent(self) -> None:
        """Sequential nexus then vault repairs on separate trees stay independent."""
        nexus = _fresh_staging("iso_nexus_vault_a")
        vault = _fresh_staging("iso_nexus_vault_b")
        _repair_tenant(nexus, "nexus")
        _repair_tenant(vault, "vault")
        assert "ClientAliveInterval 120" in _sshd_conf(nexus)
        vault_conf = _sshd_conf(vault)
        assert "ClientAliveInterval 120" not in vault_conf

    def test_rift_and_edge_sequential_repairs_independent(self) -> None:
        """Sequential rift then edge repairs on separate trees stay independent."""
        rift = _fresh_staging("iso_rift_edge_a")
        edge = _fresh_staging("iso_rift_edge_b")
        _repair_tenant(rift, "rift")
        _repair_tenant(edge, "edge")
        assert "MaxSessions 4" in _sshd_conf(rift)
        assert "LoginGraceTime 90" in _sshd_conf(edge)
        assert "MaxSessions 4" not in _sshd_conf(edge)

    def test_prism_and_pulse_manifest_sha256_differ(self) -> None:
        """Prism and pulse first-repair manifest digests differ."""
        prism = _fresh_staging("iso_prism_pulse_a")
        pulse = _fresh_staging("iso_prism_pulse_b")
        prism_manifest = _repair_tenant(prism, "prism")
        pulse_manifest = _repair_tenant(pulse, "pulse")
        assert prism_manifest["manifest_sha256"] != pulse_manifest["manifest_sha256"]

    def test_quasar_and_orbit_audit_clean_independently(self) -> None:
        """Quasar and orbit each audit clean after tenant-scoped repair."""
        quasar = _fresh_staging("iso_quasar_orbit_a")
        orbit = _fresh_staging("iso_quasar_orbit_b")
        _repair_tenant(quasar, "quasar")
        _repair_tenant(orbit, "orbit")
        assert _audit_tenant(quasar, "quasar")["clean"] is True
        assert _audit_tenant(orbit, "orbit")["clean"] is True


class TestDeskTrapBehavioralRound2:
    def test_nexus_cache_desk_is_decoy(self) -> None:
        """Nexus cache desk exists but repair follows live overlay not cache."""
        desk = Path("/app/docs/nexus_cache_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_nexus")
        _repair_tenant(staging, "nexus")
        assert "ClientAliveInterval 120" in _sshd_conf(staging)

    def test_rift_alias_desk_is_decoy(self) -> None:
        """Rift alias desk exists but repair uses rift tenant overlay not staging."""
        desk = Path("/app/docs/rift_alias_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_rift")
        _repair_tenant(staging, "rift")
        conf = _sshd_conf(staging)
        assert "MaxSessions 4" in conf
        assert "MaxAuthTries 4" not in conf

    def test_prism_snapshot_desk_is_decoy(self) -> None:
        """Prism snapshot desk exists but repair uses live registry not snapshot alias."""
        desk = Path("/app/docs/prism_snapshot_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_prism")
        _repair_tenant(staging, "prism")
        assert "LogLevel VERBOSE" in _sshd_conf(staging)

    def test_quasar_global_first_desk_is_decoy(self) -> None:
        """Quasar global-first desk exists but tenant overlay leaves win."""
        desk = Path("/app/docs/quasar_global_first_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_quasar")
        _repair_tenant(staging, "quasar")
        conf = _sshd_conf(staging)
        assert "PermitTTY no" in conf
        allow_users = next(
            line for line in conf.splitlines() if line.startswith("AllowUsers ")
        )
        assert "alice" in allow_users
        assert "bob" not in allow_users.split("AllowUsers", 1)[-1]


class TestManifestAndAuditDepth:
    def test_nexus_manifest_changes_have_before_after_digests(self) -> None:
        """Nexus repair changes include 64-char before and after digests."""
        staging = _fresh_staging("depth_nexus")
        manifest = _repair_tenant(staging, "nexus")
        assert manifest["noop"] is False
        for change in manifest["changes"]:
            assert len(change["before_sha256"]) == 64
            assert len(change["after_sha256"]) == 64
            assert change["before_sha256"] != change["after_sha256"]

    def test_rift_manifest_hash_differs_from_wrapped_digest(self) -> None:
        """Rift manifest_sha256 is not the desk wrapped-object digest trap."""
        staging = _fresh_staging("depth_rift")
        manifest = _repair_tenant(staging, "rift")
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    def test_prism_audit_reports_sshd_setting_violations_pre_repair(self) -> None:
        """Pre-repair prism audit includes sshd_setting violations."""
        staging = _fresh_staging("depth_prism_sshd")
        report = _audit_tenant(staging, "prism", "audit_prism_sshd.json")
        kinds = {v["kind"] for v in report["violations"]}
        assert "sshd_setting" in kinds

    def test_quasar_repair_changes_sorted_by_path(self) -> None:
        """Quasar repair manifest changes are sorted by ascending path."""
        staging = _fresh_staging("depth_quasar_sort")
        manifest = _repair_tenant(staging, "quasar")
        paths = [change["path"] for change in manifest["changes"]]
        assert paths == sorted(paths)

    def test_nexus_second_repair_empty_changes_digest(self) -> None:
        """Second nexus repair emits canonical digest over empty changes array."""
        staging = _fresh_staging("depth_nexus_noop")
        _repair_tenant(staging, "nexus", "fix1.json")
        manifest = _repair_tenant(staging, "nexus", "fix2.json")
        assert manifest["changes"] == []
        assert manifest["manifest_sha256"] == _sha256_text("[]")

    def test_rift_audit_violations_include_ssh_key_mismatch(self) -> None:
        """Pre-repair rift audit flags drifted authorized_keys."""
        staging = _fresh_staging("depth_rift_keys")
        report = _audit_tenant(staging, "rift", "audit_rift_keys.json")
        kinds = {v["kind"] for v in report["violations"]}
        assert "ssh_key_mismatch" in kinds


class TestRegistryLiveReadsRound2:
    def test_nexus_live_ssh_key_mutation_reflected_in_repair(
        self,
        redis_registry: None,
    ) -> None:
        """Nexus repair writes alice key from live Redis after mutation."""
        live_key = "ssh-rsa NEXUSLIVEKEY alice@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key],
            check=True,
        )
        staging = _fresh_staging("live_nexus")
        _repair_tenant(staging, "nexus")
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_rift_cache_mutation_ignored_at_repair(self, redis_registry: None) -> None:
        """Rift repair ignores runtime cache MaxSessions override."""
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:registry:cache:rift",
                "sshd_settings",
                '{"ssh/sshd_config.d/bastion.conf":{"MaxSessions":"99"}}',
            ],
            check=True,
        )
        staging = _fresh_staging("live_rift_cache")
        _repair_tenant(staging, "rift")
        assert "MaxSessions 4" in _sshd_conf(staging)
        assert "MaxSessions 99" not in _sshd_conf(staging)

    def test_prism_live_ssh_key_audit_expected(self, redis_registry: None) -> None:
        """Prism audit expected field matches live Redis after key mutation."""
        live_key = "ssh-rsa PRISMLIVEKEY alice@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key],
            check=True,
        )
        staging = _fresh_staging("live_prism_audit")
        report = _audit_tenant(staging, "prism", "audit_prism_live.json")
        alice = [
            v
            for v in report["violations"]
            if v["path"] == "homes/alice/.ssh/authorized_keys"
            and v["kind"] == "ssh_key_mismatch"
        ]
        assert alice
        assert alice[0]["expected"] == live_key

    def test_quasar_archive_key_alias_ignored(self, redis_registry: None) -> None:
        """Quasar repair ignores bastion:ssh_keys:archive alias."""
        live_key = "ssh-rsa QUASARLIVE alice@corp"
        archive_key = "ssh-rsa QUASARARCHIVE alice@corp"
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key],
            check=True,
        )
        subprocess.run(
            ["redis-cli", "HSET", "bastion:ssh_keys:archive", "alice", archive_key],
            check=True,
        )
        staging = _fresh_staging("live_quasar_archive")
        _repair_tenant(staging, "quasar")
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_nexus_sudoers_order_from_registry(self, redis_registry: None) -> None:
        """Nexus repair preserves registry sudoers hash field order."""
        subprocess.run(["redis-cli", "DEL", "bastion:sudoers_lines"], check=True)
        subprocess.run(
            [
                "redis-cli",
                "HSET",
                "bastion:sudoers_lines",
                "rule_x",
                "omega-svc ALL=(ALL) NOPASSWD:/usr/bin/true",
                "rule_y",
                "beta-svc ALL=(ALL) NOPASSWD:/usr/bin/id",
            ],
            check=True,
        )
        staging = _fresh_staging("live_nexus_sudoers")
        _repair_tenant(staging, "nexus")
        lines = [
            line
            for line in (staging / "extracted/sudoers.d/bastion-users")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        assert lines[0].startswith("omega-svc")
        assert lines[1].startswith("beta-svc")

    def test_rift_second_repair_idempotent_on_disk(self, redis_registry: None) -> None:
        """Noop second rift repair leaves tracked file digests unchanged."""
        staging = _fresh_staging("live_rift_idempotent")
        _repair_tenant(staging, "rift", "fix1.json")
        tracked = [
            staging / "extracted/homes/alice/.ssh/authorized_keys",
            staging / "extracted/sudoers.d/bastion-users",
            staging / "extracted/ssh/sshd_config.d/bastion.conf",
        ]
        before = {str(path): _sha256_file(path) for path in tracked}
        manifest = _repair_tenant(staging, "rift", "fix2.json")
        after = {str(path): _sha256_file(path) for path in tracked}
        assert manifest["noop"] is True
        assert before == after



class TestHeldOutAuroraTenant:
    def test_aurora_overlay_applied(self) -> None:
        """Held-out aurora tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("aurora_overlay")
        manifest = _repair_tenant(staging, "aurora", "fix_aurora.json")
        assert manifest["tenant"] == "aurora"
        conf = _sshd_conf(staging)
        assert "AddressFamily inet" in conf
        assert "LoginGraceTime 45" in conf

    def test_aurora_ignores_seeded_registry_cache(self) -> None:
        """Aurora repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("aurora_cache")
        _repair_tenant(staging, "aurora")
        conf = _sshd_conf(staging)
        assert "AddressFamily inet" in conf
        assert "AddressFamily any" not in conf
        assert "LoginGraceTime 120" not in conf

    def test_aurora_tenant_audit_clean_after_repair(self) -> None:
        """Aurora repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("aurora_clean")
        _repair_tenant(staging, "aurora")
        report = _audit_tenant(staging, "aurora", "audit_aurora.json")
        assert report["tenant"] == "aurora"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True

    def test_aurora_manifest_digest_matches_sorted_changes(self) -> None:
        """Aurora manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("aurora_manifest")
        manifest = _repair_tenant(staging, "aurora")
        assert manifest["changes"] == sorted(manifest["changes"], key=lambda item: item["path"])
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    def test_aurora_second_repair_noop_preserves_files(self) -> None:
        """Second aurora repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("aurora_noop")
        _repair_tenant(staging, "aurora", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "aurora", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutHelixTenant:
    def test_helix_overlay_applied(self) -> None:
        """Held-out helix tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("helix_overlay")
        manifest = _repair_tenant(staging, "helix", "fix_helix.json")
        assert manifest["tenant"] == "helix"
        conf = _sshd_conf(staging)
        assert "HostbasedAuthentication no" in conf
        assert "IgnoreRhosts yes" in conf

    def test_helix_ignores_seeded_registry_cache(self) -> None:
        """Helix repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("helix_cache")
        _repair_tenant(staging, "helix")
        conf = _sshd_conf(staging)
        assert "HostbasedAuthentication no" in conf
        assert "HostbasedAuthentication yes" not in conf
        assert "IgnoreRhosts no" not in conf

    def test_helix_tenant_audit_clean_after_repair(self) -> None:
        """Helix repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("helix_clean")
        _repair_tenant(staging, "helix")
        report = _audit_tenant(staging, "helix", "audit_helix.json")
        assert report["tenant"] == "helix"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True

    def test_helix_manifest_digest_matches_sorted_changes(self) -> None:
        """Helix manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("helix_manifest")
        manifest = _repair_tenant(staging, "helix")
        assert manifest["changes"] == sorted(manifest["changes"], key=lambda item: item["path"])
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    def test_helix_second_repair_noop_preserves_files(self) -> None:
        """Second helix repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("helix_noop")
        _repair_tenant(staging, "helix", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "helix", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutVertexTenant:
    def test_vertex_overlay_applied(self) -> None:
        """Held-out vertex tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("vertex_overlay")
        manifest = _repair_tenant(staging, "vertex", "fix_vertex.json")
        assert manifest["tenant"] == "vertex"
        conf = _sshd_conf(staging)
        assert "PermitEmptyPasswords no" in conf
        assert "MaxStartups 10:30:100" in conf

    def test_vertex_ignores_seeded_registry_cache(self) -> None:
        """Vertex repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("vertex_cache")
        _repair_tenant(staging, "vertex")
        conf = _sshd_conf(staging)
        assert "PermitEmptyPasswords no" in conf
        assert "PermitEmptyPasswords yes" not in conf
        assert "MaxStartups 1:1:1" not in conf

    def test_vertex_tenant_audit_clean_after_repair(self) -> None:
        """Vertex repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("vertex_clean")
        _repair_tenant(staging, "vertex")
        report = _audit_tenant(staging, "vertex", "audit_vertex.json")
        assert report["tenant"] == "vertex"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True

    def test_vertex_manifest_digest_matches_sorted_changes(self) -> None:
        """Vertex manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("vertex_manifest")
        manifest = _repair_tenant(staging, "vertex")
        assert manifest["changes"] == sorted(manifest["changes"], key=lambda item: item["path"])
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    def test_vertex_second_repair_noop_preserves_files(self) -> None:
        """Second vertex repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("vertex_noop")
        _repair_tenant(staging, "vertex", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "vertex", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutContinuumTenant:
    def test_continuum_overlay_applied(self) -> None:
        """Held-out continuum tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("continuum_overlay")
        manifest = _repair_tenant(staging, "continuum", "fix_continuum.json")
        assert manifest["tenant"] == "continuum"
        conf = _sshd_conf(staging)
        assert "StreamLocalBindMask 077" in conf
        assert "PermitUserEnvironment no" in conf

    def test_continuum_ignores_seeded_registry_cache(self) -> None:
        """Continuum repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("continuum_cache")
        _repair_tenant(staging, "continuum")
        conf = _sshd_conf(staging)
        assert "StreamLocalBindMask 077" in conf
        assert "StreamLocalBindMask 000" not in conf
        assert "PermitUserEnvironment yes" not in conf

    def test_continuum_tenant_audit_clean_after_repair(self) -> None:
        """Continuum repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("continuum_clean")
        _repair_tenant(staging, "continuum")
        report = _audit_tenant(staging, "continuum", "audit_continuum.json")
        assert report["tenant"] == "continuum"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True

    def test_continuum_manifest_digest_matches_sorted_changes(self) -> None:
        """Continuum manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("continuum_manifest")
        manifest = _repair_tenant(staging, "continuum")
        assert manifest["changes"] == sorted(manifest["changes"], key=lambda item: item["path"])
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    def test_continuum_second_repair_noop_preserves_files(self) -> None:
        """Second continuum repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("continuum_noop")
        _repair_tenant(staging, "continuum", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "continuum", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestDeepHardeningRoundF:

    def test_aurora_helix_overlays_do_not_cross(self, redis_registry: None) -> None:
        """Aurora and helix repairs on sibling trees keep distinct sshd directives."""
        left = _fresh_staging("aurora_helix_left")
        right = _fresh_staging("aurora_helix_right")
        _repair_tenant(left, "aurora")
        _repair_tenant(right, "helix")
        left_conf = _sshd_conf(left)
        right_conf = _sshd_conf(right)
        assert "AddressFamily inet" in left_conf
        assert "HostbasedAuthentication no" in right_conf
        assert "HostbasedAuthentication no" not in left_conf
        assert "AddressFamily inet" not in right_conf

    def test_vertex_continuum_overlays_do_not_cross(self, redis_registry: None) -> None:
        """Vertex and continuum repairs on sibling trees keep distinct sshd directives."""
        left = _fresh_staging("vertex_continuum_left")
        right = _fresh_staging("vertex_continuum_right")
        _repair_tenant(left, "vertex")
        _repair_tenant(right, "continuum")
        left_conf = _sshd_conf(left)
        right_conf = _sshd_conf(right)
        assert "PermitEmptyPasswords no" in left_conf
        assert "StreamLocalBindMask 077" in right_conf
        assert "StreamLocalBindMask 077" not in left_conf
        assert "PermitEmptyPasswords no" not in right_conf

    def test_aurora_vertex_overlays_do_not_cross(self, redis_registry: None) -> None:
        """Aurora and vertex repairs on sibling trees keep distinct sshd directives."""
        left = _fresh_staging("aurora_vertex_left")
        right = _fresh_staging("aurora_vertex_right")
        _repair_tenant(left, "aurora")
        _repair_tenant(right, "vertex")
        left_conf = _sshd_conf(left)
        right_conf = _sshd_conf(right)
        assert "AddressFamily inet" in left_conf
        assert "PermitEmptyPasswords no" in right_conf
        assert "PermitEmptyPasswords no" not in left_conf
        assert "AddressFamily inet" not in right_conf

    def test_helix_continuum_overlays_do_not_cross(self, redis_registry: None) -> None:
        """Helix and continuum repairs on sibling trees keep distinct sshd directives."""
        left = _fresh_staging("helix_continuum_left")
        right = _fresh_staging("helix_continuum_right")
        _repair_tenant(left, "helix")
        _repair_tenant(right, "continuum")
        left_conf = _sshd_conf(left)
        right_conf = _sshd_conf(right)
        assert "HostbasedAuthentication no" in left_conf
        assert "StreamLocalBindMask 077" in right_conf
        assert "StreamLocalBindMask 077" not in left_conf
        assert "HostbasedAuthentication no" not in right_conf

    def test_aurora_ignores_runtime_stale_cache(self, redis_registry: None) -> None:
        """Aurora repair ignores freshly written stale cache sshd_settings."""
        subprocess.run(
            ["redis-cli", "HSET", "bastion:registry:cache:aurora", "sshd_settings",
             '{"ssh/sshd_config.d/bastion.conf":{"AddressFamily":"any","LoginGraceTime":"999"}}'],
            check=True,
        )
        staging = _fresh_staging("aurora_runtime_cache")
        _repair_tenant(staging, "aurora")
        conf = _sshd_conf(staging)
        assert "AddressFamily inet" in conf
        assert "AddressFamily any" not in conf

    def test_helix_ignores_runtime_stale_cache(self, redis_registry: None) -> None:
        """Helix repair ignores freshly written stale cache sshd_settings."""
        subprocess.run(
            ["redis-cli", "HSET", "bastion:registry:cache:helix", "sshd_settings",
             '{"ssh/sshd_config.d/bastion.conf":{"HostbasedAuthentication":"yes","IgnoreRhosts":"no"}}'],
            check=True,
        )
        staging = _fresh_staging("helix_runtime_cache")
        _repair_tenant(staging, "helix")
        conf = _sshd_conf(staging)
        assert "HostbasedAuthentication no" in conf
        assert "HostbasedAuthentication yes" not in conf

    def test_vertex_sixth_repair_still_noop(self) -> None:
        """Sixth vertex repair remains noop with stable empty-array digest."""
        staging = _fresh_staging("vertex_sixth")
        for index in range(1, 6):
            _repair_tenant(staging, "vertex", f"fix{index}.json")
        manifest = _repair_tenant(staging, "vertex", "fix6.json")
        assert manifest["noop"] is True
        assert manifest["manifest_sha256"] == _manifest_hash([])

    def test_continuum_sixth_repair_still_noop(self) -> None:
        """Sixth continuum repair remains noop with stable empty-array digest."""
        staging = _fresh_staging("continuum_sixth")
        for index in range(1, 6):
            _repair_tenant(staging, "continuum", f"fix{index}.json")
        manifest = _repair_tenant(staging, "continuum", "fix6.json")
        assert manifest["noop"] is True
        assert manifest["manifest_sha256"] == _manifest_hash([])


class TestDeepHardeningRoundG:

    def test_aurora_and_prod_repairs_remain_distinct(self) -> None:
        """Aurora and prod sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundg_aurora")
        b = _fresh_staging("roundg_prod")
        _repair_tenant(a, "aurora")
        _repair_tenant(b, "prod")
        assert "AddressFamily inet" in _sshd_conf(a)
        assert "PermitRootLogin prohibit-password" in _sshd_conf(b)
        assert "PermitRootLogin prohibit-password" not in _sshd_conf(a)

    def test_helix_and_nexus_repairs_remain_distinct(self) -> None:
        """Helix and nexus sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundg_helix")
        b = _fresh_staging("roundg_nexus")
        _repair_tenant(a, "helix")
        _repair_tenant(b, "nexus")
        assert "HostbasedAuthentication no" in _sshd_conf(a)
        assert "ClientAliveInterval 120" in _sshd_conf(b)
        assert "ClientAliveInterval 120" not in _sshd_conf(a)

    def test_vertex_and_rift_repairs_remain_distinct(self) -> None:
        """Vertex and rift sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundg_vertex")
        b = _fresh_staging("roundg_rift")
        _repair_tenant(a, "vertex")
        _repair_tenant(b, "rift")
        assert "PermitEmptyPasswords no" in _sshd_conf(a)
        assert "MaxSessions 4" in _sshd_conf(b)
        assert "MaxSessions 4" not in _sshd_conf(a)

    def test_continuum_and_prism_repairs_remain_distinct(self) -> None:
        """Continuum and prism sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundg_continuum")
        b = _fresh_staging("roundg_prism")
        _repair_tenant(a, "continuum")
        _repair_tenant(b, "prism")
        assert "StreamLocalBindMask 077" in _sshd_conf(a)
        assert "LogLevel VERBOSE" in _sshd_conf(b)
        assert "LogLevel VERBOSE" not in _sshd_conf(a)

    def test_aurora_and_atlas_repairs_remain_distinct(self) -> None:
        """Aurora and atlas sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundg_aurora")
        b = _fresh_staging("roundg_atlas")
        _repair_tenant(a, "aurora")
        _repair_tenant(b, "atlas")
        assert "AddressFamily inet" in _sshd_conf(a)
        assert "Compression yes" in _sshd_conf(b)
        assert "Compression yes" not in _sshd_conf(a)

    def test_helix_and_comet_repairs_remain_distinct(self) -> None:
        """Helix and comet sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundg_helix")
        b = _fresh_staging("roundg_comet")
        _repair_tenant(a, "helix")
        _repair_tenant(b, "comet")
        assert "HostbasedAuthentication no" in _sshd_conf(a)
        assert "Banner /etc/issue.net" in _sshd_conf(b)
        assert "Banner /etc/issue.net" not in _sshd_conf(a)

    def test_vertex_and_orbit_audit_clean_independently(self) -> None:
        """Vertex and orbit each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundg_audit_vertex")
        b = _fresh_staging("roundg_audit_orbit")
        _repair_tenant(a, "vertex")
        _repair_tenant(b, "orbit")
        assert _audit_tenant(a, "vertex")["clean"] is True
        assert _audit_tenant(b, "orbit")["clean"] is True

    def test_continuum_and_pulse_audit_clean_independently(self) -> None:
        """Continuum and pulse each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundg_audit_continuum")
        b = _fresh_staging("roundg_audit_pulse")
        _repair_tenant(a, "continuum")
        _repair_tenant(b, "pulse")
        assert _audit_tenant(a, "continuum")["clean"] is True
        assert _audit_tenant(b, "pulse")["clean"] is True

    def test_aurora_and_vault_audit_clean_independently(self) -> None:
        """Aurora and vault each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundg_audit_aurora")
        b = _fresh_staging("roundg_audit_vault")
        _repair_tenant(a, "aurora")
        _repair_tenant(b, "vault")
        assert _audit_tenant(a, "aurora")["clean"] is True
        assert _audit_tenant(b, "vault")["clean"] is True

    def test_helix_and_edge_audit_clean_independently(self) -> None:
        """Helix and edge each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundg_audit_helix")
        b = _fresh_staging("roundg_audit_edge")
        _repair_tenant(a, "helix")
        _repair_tenant(b, "edge")
        assert _audit_tenant(a, "helix")["clean"] is True
        assert _audit_tenant(b, "edge")["clean"] is True


class TestBehavioralIntegrityRound3:

    def test_aurora_pre_repair_audit_includes_ssh_key_mismatch(self) -> None:
        """Pre-repair aurora audit reports ssh_key_mismatch violations."""
        staging = _fresh_staging("bir3_aurora_ssh_key_mismatch")
        report = _audit_tenant(staging, "aurora", "audit_aurora_ssh_key_mismatch.json")
        kinds = {v["kind"] for v in report["violations"]}
        assert "ssh_key_mismatch" in kinds

    def test_helix_pre_repair_audit_includes_sshd_setting(self) -> None:
        """Pre-repair helix audit reports sshd_setting violations."""
        staging = _fresh_staging("bir3_helix_sshd_setting")
        report = _audit_tenant(staging, "helix", "audit_helix_sshd_setting.json")
        kinds = {v["kind"] for v in report["violations"]}
        assert "sshd_setting" in kinds

    def test_vertex_pre_repair_audit_includes_mode_mismatch(self) -> None:
        """Pre-repair vertex audit reports mode_mismatch violations."""
        staging = _fresh_staging("bir3_vertex_mode_mismatch")
        report = _audit_tenant(staging, "vertex", "audit_vertex_mode_mismatch.json")
        kinds = {v["kind"] for v in report["violations"]}
        assert "mode_mismatch" in kinds

    def test_continuum_pre_repair_audit_includes_sudoers_unauthorized(self) -> None:
        """Pre-repair continuum audit reports sudoers_unauthorized violations."""
        staging = _fresh_staging("bir3_continuum_sudoers_unauthorized")
        report = _audit_tenant(staging, "continuum", "audit_continuum_sudoers_unauthorized.json")
        kinds = {v["kind"] for v in report["violations"]}
        assert "sudoers_unauthorized" in kinds

    def test_aurora_repair_changes_have_path_digests(self) -> None:
        """Aurora repair changes include before and after content digests."""
        staging = _fresh_staging("bir3_aurora_digests")
        manifest = _repair_tenant(staging, "aurora")
        assert manifest["noop"] is False
        for change in manifest["changes"]:
            assert set(change) == {"path", "before_sha256", "after_sha256"}
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

    def test_helix_repair_changes_have_path_digests(self) -> None:
        """Helix repair changes include before and after content digests."""
        staging = _fresh_staging("bir3_helix_digests")
        manifest = _repair_tenant(staging, "helix")
        assert manifest["noop"] is False
        for change in manifest["changes"]:
            assert set(change) == {"path", "before_sha256", "after_sha256"}
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

    def test_vertex_repair_changes_have_path_digests(self) -> None:
        """Vertex repair changes include before and after content digests."""
        staging = _fresh_staging("bir3_vertex_digests")
        manifest = _repair_tenant(staging, "vertex")
        assert manifest["noop"] is False
        for change in manifest["changes"]:
            assert set(change) == {"path", "before_sha256", "after_sha256"}
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

    def test_continuum_repair_changes_have_path_digests(self) -> None:
        """Continuum repair changes include before and after content digests."""
        staging = _fresh_staging("bir3_continuum_digests")
        manifest = _repair_tenant(staging, "continuum")
        assert manifest["noop"] is False
        for change in manifest["changes"]:
            assert set(change) == {"path", "before_sha256", "after_sha256"}
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

    def test_aurora_audit_violations_sorted_lexicographically(self) -> None:
        """Pre-repair aurora audit violations sorted by path then kind."""
        staging = _fresh_staging("bir3_aurora_sort")
        report = _audit_tenant(staging, "aurora", "audit_aurora_sort.json")
        assert report["violations"] == sorted(report["violations"], key=lambda item: (item["path"], item["kind"]))

    def test_helix_audit_violations_sorted_lexicographically(self) -> None:
        """Pre-repair helix audit violations sorted by path then kind."""
        staging = _fresh_staging("bir3_helix_sort")
        report = _audit_tenant(staging, "helix", "audit_helix_sort.json")
        assert report["violations"] == sorted(report["violations"], key=lambda item: (item["path"], item["kind"]))


class TestCrossTenantIsolationRound3:

    def test_aurora_and_nexus_manifest_tenants_differ(self) -> None:
        """Aurora and nexus repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_aurora_nexus_l")
        right = _fresh_staging("iso3_aurora_nexus_r")
        ma = _repair_tenant(left, "aurora")
        mb = _repair_tenant(right, "nexus")
        assert ma["tenant"] == "aurora"
        assert mb["tenant"] == "nexus"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_helix_and_rift_manifest_tenants_differ(self) -> None:
        """Helix and rift repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_helix_rift_l")
        right = _fresh_staging("iso3_helix_rift_r")
        ma = _repair_tenant(left, "helix")
        mb = _repair_tenant(right, "rift")
        assert ma["tenant"] == "helix"
        assert mb["tenant"] == "rift"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_vertex_and_prism_manifest_tenants_differ(self) -> None:
        """Vertex and prism repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_vertex_prism_l")
        right = _fresh_staging("iso3_vertex_prism_r")
        ma = _repair_tenant(left, "vertex")
        mb = _repair_tenant(right, "prism")
        assert ma["tenant"] == "vertex"
        assert mb["tenant"] == "prism"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_continuum_and_quasar_manifest_tenants_differ(self) -> None:
        """Continuum and quasar repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_continuum_quasar_l")
        right = _fresh_staging("iso3_continuum_quasar_r")
        ma = _repair_tenant(left, "continuum")
        mb = _repair_tenant(right, "quasar")
        assert ma["tenant"] == "continuum"
        assert mb["tenant"] == "quasar"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_aurora_and_pulse_manifest_tenants_differ(self) -> None:
        """Aurora and pulse repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_aurora_pulse_l")
        right = _fresh_staging("iso3_aurora_pulse_r")
        ma = _repair_tenant(left, "aurora")
        mb = _repair_tenant(right, "pulse")
        assert ma["tenant"] == "aurora"
        assert mb["tenant"] == "pulse"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_helix_and_orbit_manifest_tenants_differ(self) -> None:
        """Helix and orbit repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_helix_orbit_l")
        right = _fresh_staging("iso3_helix_orbit_r")
        ma = _repair_tenant(left, "helix")
        mb = _repair_tenant(right, "orbit")
        assert ma["tenant"] == "helix"
        assert mb["tenant"] == "orbit"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_vertex_and_comet_manifest_tenants_differ(self) -> None:
        """Vertex and comet repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_vertex_comet_l")
        right = _fresh_staging("iso3_vertex_comet_r")
        ma = _repair_tenant(left, "vertex")
        mb = _repair_tenant(right, "comet")
        assert ma["tenant"] == "vertex"
        assert mb["tenant"] == "comet"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_continuum_and_atlas_manifest_tenants_differ(self) -> None:
        """Continuum and atlas repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_continuum_atlas_l")
        right = _fresh_staging("iso3_continuum_atlas_r")
        ma = _repair_tenant(left, "continuum")
        mb = _repair_tenant(right, "atlas")
        assert ma["tenant"] == "continuum"
        assert mb["tenant"] == "atlas"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_aurora_and_dr_manifest_tenants_differ(self) -> None:
        """Aurora and dr repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_aurora_dr_l")
        right = _fresh_staging("iso3_aurora_dr_r")
        ma = _repair_tenant(left, "aurora")
        mb = _repair_tenant(right, "dr")
        assert ma["tenant"] == "aurora"
        assert mb["tenant"] == "dr"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_helix_and_canary_manifest_tenants_differ(self) -> None:
        """Helix and canary repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_helix_canary_l")
        right = _fresh_staging("iso3_helix_canary_r")
        ma = _repair_tenant(left, "helix")
        mb = _repair_tenant(right, "canary")
        assert ma["tenant"] == "helix"
        assert mb["tenant"] == "canary"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_vertex_and_staging_manifest_tenants_differ(self) -> None:
        """Vertex and staging repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_vertex_staging_l")
        right = _fresh_staging("iso3_vertex_staging_r")
        ma = _repair_tenant(left, "vertex")
        mb = _repair_tenant(right, "staging")
        assert ma["tenant"] == "vertex"
        assert mb["tenant"] == "staging"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_continuum_and_edge_manifest_tenants_differ(self) -> None:
        """Continuum and edge repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_continuum_edge_l")
        right = _fresh_staging("iso3_continuum_edge_r")
        ma = _repair_tenant(left, "continuum")
        mb = _repair_tenant(right, "edge")
        assert ma["tenant"] == "continuum"
        assert mb["tenant"] == "edge"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_aurora_and_vault_manifest_tenants_differ(self) -> None:
        """Aurora and vault repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_aurora_vault_l")
        right = _fresh_staging("iso3_aurora_vault_r")
        ma = _repair_tenant(left, "aurora")
        mb = _repair_tenant(right, "vault")
        assert ma["tenant"] == "aurora"
        assert mb["tenant"] == "vault"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_helix_and_prod_manifest_tenants_differ(self) -> None:
        """Helix and prod repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_helix_prod_l")
        right = _fresh_staging("iso3_helix_prod_r")
        ma = _repair_tenant(left, "helix")
        mb = _repair_tenant(right, "prod")
        assert ma["tenant"] == "helix"
        assert mb["tenant"] == "prod"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_vertex_and_nexus_manifest_tenants_differ(self) -> None:
        """Vertex and nexus repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_vertex_nexus_l")
        right = _fresh_staging("iso3_vertex_nexus_r")
        ma = _repair_tenant(left, "vertex")
        mb = _repair_tenant(right, "nexus")
        assert ma["tenant"] == "vertex"
        assert mb["tenant"] == "nexus"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_continuum_and_rift_manifest_tenants_differ(self) -> None:
        """Continuum and rift repair manifests record distinct tenant ids."""
        left = _fresh_staging("iso3_continuum_rift_l")
        right = _fresh_staging("iso3_continuum_rift_r")
        ma = _repair_tenant(left, "continuum")
        mb = _repair_tenant(right, "rift")
        assert ma["tenant"] == "continuum"
        assert mb["tenant"] == "rift"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]


class TestDeskTrapBehavioralRound3:

    def test_aurora_aurora_cache_desk_is_decoy(self) -> None:
        """aurora_cache_desk.md exists but repair follows live overlay not desk circulation."""
        desk_path = Path("/app/docs/aurora_cache_desk.md")
        assert desk_path.is_file()
        assert "CACHE_PRIORITY" in desk_path.read_text(encoding="utf-8")
        staging = _fresh_staging("desk3_aurora")
        _repair_tenant(staging, "aurora")
        assert "AddressFamily inet" in _sshd_conf(staging)

    def test_helix_helix_alias_desk_is_decoy(self) -> None:
        """helix_alias_desk.md exists but repair follows live overlay not desk circulation."""
        desk_path = Path("/app/docs/helix_alias_desk.md")
        assert desk_path.is_file()
        assert "HELIX_TENANT" in desk_path.read_text(encoding="utf-8")
        staging = _fresh_staging("desk3_helix")
        _repair_tenant(staging, "helix")
        assert "HostbasedAuthentication no" in _sshd_conf(staging)

    def test_vertex_vertex_snapshot_desk_is_decoy(self) -> None:
        """vertex_snapshot_desk.md exists but repair follows live overlay not desk circulation."""
        desk_path = Path("/app/docs/vertex_snapshot_desk.md")
        assert desk_path.is_file()
        assert "REGISTRY_SOURCE" in desk_path.read_text(encoding="utf-8")
        staging = _fresh_staging("desk3_vertex")
        _repair_tenant(staging, "vertex")
        assert "PermitEmptyPasswords no" in _sshd_conf(staging)

    def test_continuum_continuum_global_first_desk_is_decoy(self) -> None:
        """continuum_global_first_desk.md exists but repair follows live overlay not desk circulation."""
        desk_path = Path("/app/docs/continuum_global_first_desk.md")
        assert desk_path.is_file()
        assert "MERGE_STRATEGY" in desk_path.read_text(encoding="utf-8")
        staging = _fresh_staging("desk3_continuum")
        _repair_tenant(staging, "continuum")
        assert "StreamLocalBindMask 077" in _sshd_conf(staging)


class TestManifestAndAuditDepthRound2:

    def test_aurora_empty_changes_digest_after_second_repair(self) -> None:
        """Second aurora repair emits canonical digest over empty changes array."""
        staging = _fresh_staging("depth2_aurora_noop")
        _repair_tenant(staging, "aurora", "fix1.json")
        manifest = _repair_tenant(staging, "aurora", "fix2.json")
        assert manifest["changes"] == []
        assert manifest["manifest_sha256"] == _sha256_text("[]")

    def test_aurora_audit_reports_tenant_and_not_clean_pre_repair(self) -> None:
        """Pre-repair aurora audit includes tenant field and clean is false."""
        staging = _fresh_staging("depth2_aurora_pre")
        report = _audit_tenant(staging, "aurora", "audit_aurora_pre.json")
        assert report["tenant"] == "aurora"
        assert report["clean"] is False
        assert report["violations"]

    def test_aurora_repair_manifest_staging_root_absolute(self) -> None:
        """Aurora repair manifest staging_root is absolute extracted path."""
        staging = _fresh_staging("depth2_aurora_root")
        manifest = _repair_tenant(staging, "aurora")
        assert manifest["staging_root"].startswith("/")
        assert manifest["staging_root"].endswith("/extracted")

    def test_helix_empty_changes_digest_after_second_repair(self) -> None:
        """Second helix repair emits canonical digest over empty changes array."""
        staging = _fresh_staging("depth2_helix_noop")
        _repair_tenant(staging, "helix", "fix1.json")
        manifest = _repair_tenant(staging, "helix", "fix2.json")
        assert manifest["changes"] == []
        assert manifest["manifest_sha256"] == _sha256_text("[]")

    def test_helix_audit_reports_tenant_and_not_clean_pre_repair(self) -> None:
        """Pre-repair helix audit includes tenant field and clean is false."""
        staging = _fresh_staging("depth2_helix_pre")
        report = _audit_tenant(staging, "helix", "audit_helix_pre.json")
        assert report["tenant"] == "helix"
        assert report["clean"] is False
        assert report["violations"]

    def test_helix_repair_manifest_staging_root_absolute(self) -> None:
        """Helix repair manifest staging_root is absolute extracted path."""
        staging = _fresh_staging("depth2_helix_root")
        manifest = _repair_tenant(staging, "helix")
        assert manifest["staging_root"].startswith("/")
        assert manifest["staging_root"].endswith("/extracted")

    def test_vertex_empty_changes_digest_after_second_repair(self) -> None:
        """Second vertex repair emits canonical digest over empty changes array."""
        staging = _fresh_staging("depth2_vertex_noop")
        _repair_tenant(staging, "vertex", "fix1.json")
        manifest = _repair_tenant(staging, "vertex", "fix2.json")
        assert manifest["changes"] == []
        assert manifest["manifest_sha256"] == _sha256_text("[]")

    def test_vertex_audit_reports_tenant_and_not_clean_pre_repair(self) -> None:
        """Pre-repair vertex audit includes tenant field and clean is false."""
        staging = _fresh_staging("depth2_vertex_pre")
        report = _audit_tenant(staging, "vertex", "audit_vertex_pre.json")
        assert report["tenant"] == "vertex"
        assert report["clean"] is False
        assert report["violations"]

    def test_vertex_repair_manifest_staging_root_absolute(self) -> None:
        """Vertex repair manifest staging_root is absolute extracted path."""
        staging = _fresh_staging("depth2_vertex_root")
        manifest = _repair_tenant(staging, "vertex")
        assert manifest["staging_root"].startswith("/")
        assert manifest["staging_root"].endswith("/extracted")

    def test_continuum_empty_changes_digest_after_second_repair(self) -> None:
        """Second continuum repair emits canonical digest over empty changes array."""
        staging = _fresh_staging("depth2_continuum_noop")
        _repair_tenant(staging, "continuum", "fix1.json")
        manifest = _repair_tenant(staging, "continuum", "fix2.json")
        assert manifest["changes"] == []
        assert manifest["manifest_sha256"] == _sha256_text("[]")

    def test_continuum_audit_reports_tenant_and_not_clean_pre_repair(self) -> None:
        """Pre-repair continuum audit includes tenant field and clean is false."""
        staging = _fresh_staging("depth2_continuum_pre")
        report = _audit_tenant(staging, "continuum", "audit_continuum_pre.json")
        assert report["tenant"] == "continuum"
        assert report["clean"] is False
        assert report["violations"]

    def test_continuum_repair_manifest_staging_root_absolute(self) -> None:
        """Continuum repair manifest staging_root is absolute extracted path."""
        staging = _fresh_staging("depth2_continuum_root")
        manifest = _repair_tenant(staging, "continuum")
        assert manifest["staging_root"].startswith("/")
        assert manifest["staging_root"].endswith("/extracted")


class TestRegistryLiveReadsRound3:

    def test_aurora_live_alice_key_mutation_reflected(self, redis_registry: None) -> None:
        """Aurora repair writes alice key from live Redis after mutation."""
        live_key = "ssh-rsa AURORALIVEKEY alice@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key], check=True)
        staging = _fresh_staging("live3_aurora_alice")
        _repair_tenant(staging, "aurora")
        key = (staging / "extracted/homes/alice/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_aurora_archive_key_alias_ignored(self, redis_registry: None) -> None:
        """Aurora repair ignores bastion:ssh_keys:archive alias for bob."""
        live_key = "ssh-rsa AURORABOBLIVE bob@corp"
        archive_key = "ssh-rsa AURORABOBARCHIVE bob@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "bob", live_key], check=True)
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys:archive", "bob", archive_key], check=True)
        staging = _fresh_staging("live3_aurora_bob")
        _repair_tenant(staging, "aurora")
        key = (staging / "extracted/homes/bob/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_aurora_cache_runtime_override_ignored(self, redis_registry: None) -> None:
        subprocess.run(
            ["redis-cli", "HSET", "bastion:registry:cache:aurora", "sshd_settings",
             '{"ssh/sshd_config.d/bastion.conf":{"AddressFamily":"any"}}'],
            check=True,
        )
        staging = _fresh_staging("live3_aurora_cache")
        _repair_tenant(staging, "aurora")
        conf = _sshd_conf(staging)
        assert "AddressFamily inet" in conf
        assert "AddressFamily any" not in conf

    def test_aurora_sudoers_registry_order_preserved(self, redis_registry: None) -> None:
        """Aurora repair preserves mutated registry sudoers hash field order."""
        subprocess.run(["redis-cli", "DEL", "bastion:sudoers_lines"], check=True)
        subprocess.run(
            ["redis-cli", "HSET", "bastion:sudoers_lines",
             "rule_aurora_a", "delta-svc ALL=(ALL) NOPASSWD:/usr/bin/true",
             "rule_aurora_b", "gamma-svc ALL=(ALL) NOPASSWD:/usr/bin/id"],
            check=True,
        )
        staging = _fresh_staging("live3_aurora_sudoers")
        _repair_tenant(staging, "aurora")
        sudo_lines = [line for line in (staging / "extracted/sudoers.d/bastion-users").read_text(encoding="utf-8").splitlines() if line.strip()]
        assert sudo_lines[0].startswith("delta-svc")
        assert sudo_lines[1].startswith("gamma-svc")

    def test_helix_live_alice_key_mutation_reflected(self, redis_registry: None) -> None:
        """Helix repair writes alice key from live Redis after mutation."""
        live_key = "ssh-rsa HELIXLIVEKEY alice@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key], check=True)
        staging = _fresh_staging("live3_helix_alice")
        _repair_tenant(staging, "helix")
        key = (staging / "extracted/homes/alice/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_helix_archive_key_alias_ignored(self, redis_registry: None) -> None:
        """Helix repair ignores bastion:ssh_keys:archive alias for bob."""
        live_key = "ssh-rsa HELIXBOBLIVE bob@corp"
        archive_key = "ssh-rsa HELIXBOBARCHIVE bob@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "bob", live_key], check=True)
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys:archive", "bob", archive_key], check=True)
        staging = _fresh_staging("live3_helix_bob")
        _repair_tenant(staging, "helix")
        key = (staging / "extracted/homes/bob/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_helix_cache_runtime_override_ignored(self, redis_registry: None) -> None:
        subprocess.run(
            ["redis-cli", "HSET", "bastion:registry:cache:helix", "sshd_settings",
             '{"ssh/sshd_config.d/bastion.conf":{"HostbasedAuthentication":"yes"}}'],
            check=True,
        )
        staging = _fresh_staging("live3_helix_cache")
        _repair_tenant(staging, "helix")
        conf = _sshd_conf(staging)
        assert "HostbasedAuthentication no" in conf
        assert "HostbasedAuthentication yes" not in conf

    def test_helix_sudoers_registry_order_preserved(self, redis_registry: None) -> None:
        """Helix repair preserves mutated registry sudoers hash field order."""
        subprocess.run(["redis-cli", "DEL", "bastion:sudoers_lines"], check=True)
        subprocess.run(
            ["redis-cli", "HSET", "bastion:sudoers_lines",
             "rule_helix_a", "delta-svc ALL=(ALL) NOPASSWD:/usr/bin/true",
             "rule_helix_b", "gamma-svc ALL=(ALL) NOPASSWD:/usr/bin/id"],
            check=True,
        )
        staging = _fresh_staging("live3_helix_sudoers")
        _repair_tenant(staging, "helix")
        sudo_lines = [line for line in (staging / "extracted/sudoers.d/bastion-users").read_text(encoding="utf-8").splitlines() if line.strip()]
        assert sudo_lines[0].startswith("delta-svc")
        assert sudo_lines[1].startswith("gamma-svc")

    def test_vertex_live_alice_key_mutation_reflected(self, redis_registry: None) -> None:
        """Vertex repair writes alice key from live Redis after mutation."""
        live_key = "ssh-rsa VERTEXLIVEKEY alice@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key], check=True)
        staging = _fresh_staging("live3_vertex_alice")
        _repair_tenant(staging, "vertex")
        key = (staging / "extracted/homes/alice/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_vertex_archive_key_alias_ignored(self, redis_registry: None) -> None:
        """Vertex repair ignores bastion:ssh_keys:archive alias for bob."""
        live_key = "ssh-rsa VERTEXBOBLIVE bob@corp"
        archive_key = "ssh-rsa VERTEXBOBARCHIVE bob@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "bob", live_key], check=True)
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys:archive", "bob", archive_key], check=True)
        staging = _fresh_staging("live3_vertex_bob")
        _repair_tenant(staging, "vertex")
        key = (staging / "extracted/homes/bob/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_vertex_cache_runtime_override_ignored(self, redis_registry: None) -> None:
        subprocess.run(
            ["redis-cli", "HSET", "bastion:registry:cache:vertex", "sshd_settings",
             '{"ssh/sshd_config.d/bastion.conf":{"PermitEmptyPasswords":"yes"}}'],
            check=True,
        )
        staging = _fresh_staging("live3_vertex_cache")
        _repair_tenant(staging, "vertex")
        conf = _sshd_conf(staging)
        assert "PermitEmptyPasswords no" in conf
        assert "PermitEmptyPasswords yes" not in conf

    def test_vertex_sudoers_registry_order_preserved(self, redis_registry: None) -> None:
        """Vertex repair preserves mutated registry sudoers hash field order."""
        subprocess.run(["redis-cli", "DEL", "bastion:sudoers_lines"], check=True)
        subprocess.run(
            ["redis-cli", "HSET", "bastion:sudoers_lines",
             "rule_vertex_a", "delta-svc ALL=(ALL) NOPASSWD:/usr/bin/true",
             "rule_vertex_b", "gamma-svc ALL=(ALL) NOPASSWD:/usr/bin/id"],
            check=True,
        )
        staging = _fresh_staging("live3_vertex_sudoers")
        _repair_tenant(staging, "vertex")
        sudo_lines = [line for line in (staging / "extracted/sudoers.d/bastion-users").read_text(encoding="utf-8").splitlines() if line.strip()]
        assert sudo_lines[0].startswith("delta-svc")
        assert sudo_lines[1].startswith("gamma-svc")

    def test_continuum_live_alice_key_mutation_reflected(self, redis_registry: None) -> None:
        """Continuum repair writes alice key from live Redis after mutation."""
        live_key = "ssh-rsa CONTINUUMLIVEKEY alice@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "alice", live_key], check=True)
        staging = _fresh_staging("live3_continuum_alice")
        _repair_tenant(staging, "continuum")
        key = (staging / "extracted/homes/alice/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_continuum_archive_key_alias_ignored(self, redis_registry: None) -> None:
        """Continuum repair ignores bastion:ssh_keys:archive alias for bob."""
        live_key = "ssh-rsa CONTINUUMBOBLIVE bob@corp"
        archive_key = "ssh-rsa CONTINUUMBOBARCHIVE bob@corp"
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys", "bob", live_key], check=True)
        subprocess.run(["redis-cli", "HSET", "bastion:ssh_keys:archive", "bob", archive_key], check=True)
        staging = _fresh_staging("live3_continuum_bob")
        _repair_tenant(staging, "continuum")
        key = (staging / "extracted/homes/bob/.ssh/authorized_keys").read_text(encoding="utf-8").strip()
        assert key == live_key

    def test_continuum_cache_runtime_override_ignored(self, redis_registry: None) -> None:
        subprocess.run(
            ["redis-cli", "HSET", "bastion:registry:cache:continuum", "sshd_settings",
             '{"ssh/sshd_config.d/bastion.conf":{"PermitUserEnvironment":"yes"}}'],
            check=True,
        )
        staging = _fresh_staging("live3_continuum_cache")
        _repair_tenant(staging, "continuum")
        conf = _sshd_conf(staging)
        assert "StreamLocalBindMask 077" in conf
        assert "StreamLocalBindMask 000" not in conf

    def test_continuum_sudoers_registry_order_preserved(self, redis_registry: None) -> None:
        """Continuum repair preserves mutated registry sudoers hash field order."""
        subprocess.run(["redis-cli", "DEL", "bastion:sudoers_lines"], check=True)
        subprocess.run(
            ["redis-cli", "HSET", "bastion:sudoers_lines",
             "rule_continuum_a", "delta-svc ALL=(ALL) NOPASSWD:/usr/bin/true",
             "rule_continuum_b", "gamma-svc ALL=(ALL) NOPASSWD:/usr/bin/id"],
            check=True,
        )
        staging = _fresh_staging("live3_continuum_sudoers")
        _repair_tenant(staging, "continuum")
        sudo_lines = [line for line in (staging / "extracted/sudoers.d/bastion-users").read_text(encoding="utf-8").splitlines() if line.strip()]
        assert sudo_lines[0].startswith("delta-svc")
        assert sudo_lines[1].startswith("gamma-svc")


class TestRepairSequenceDepth:

    def test_aurora_fourth_repair_still_noop(self) -> None:
        """Fourth aurora repair remains noop."""
        staging = _fresh_staging("seq_aurora_fourth")
        for index in range(1, 4):
            _repair_tenant(staging, "aurora", f"fix{index}.json")
        manifest = _repair_tenant(staging, "aurora", "fix4.json")
        assert manifest["noop"] is True

    def test_aurora_first_and_second_manifest_hashes_differ_then_stable(self) -> None:
        """Aurora first repair manifest hash differs from second noop digest."""
        staging = _fresh_staging("seq_aurora_hash")
        first = _repair_tenant(staging, "aurora", "fix1.json")
        second = _repair_tenant(staging, "aurora", "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])

    def test_aurora_triple_repair_idempotent_on_disk(self) -> None:
        """Third aurora repair leaves tracked staging file digests unchanged."""
        staging = _fresh_staging("seq_aurora_triple")
        _repair_tenant(staging, "aurora", "fix1.json")
        _repair_tenant(staging, "aurora", "fix2.json")
        tracked = [
            staging / "extracted/homes/alice/.ssh/authorized_keys",
            staging / "extracted/sudoers.d/bastion-users",
            staging / "extracted/ssh/sshd_config.d/bastion.conf",
        ]
        before = {str(path): _sha256_file(path) for path in tracked}
        manifest = _repair_tenant(staging, "aurora", "fix3.json")
        after = {str(path): _sha256_file(path) for path in tracked}
        assert manifest["noop"] is True
        assert before == after

    def test_helix_fourth_repair_still_noop(self) -> None:
        """Fourth helix repair remains noop."""
        staging = _fresh_staging("seq_helix_fourth")
        for index in range(1, 4):
            _repair_tenant(staging, "helix", f"fix{index}.json")
        manifest = _repair_tenant(staging, "helix", "fix4.json")
        assert manifest["noop"] is True

    def test_helix_first_and_second_manifest_hashes_differ_then_stable(self) -> None:
        """Helix first repair manifest hash differs from second noop digest."""
        staging = _fresh_staging("seq_helix_hash")
        first = _repair_tenant(staging, "helix", "fix1.json")
        second = _repair_tenant(staging, "helix", "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])

    def test_helix_triple_repair_idempotent_on_disk(self) -> None:
        """Third helix repair leaves tracked staging file digests unchanged."""
        staging = _fresh_staging("seq_helix_triple")
        _repair_tenant(staging, "helix", "fix1.json")
        _repair_tenant(staging, "helix", "fix2.json")
        tracked = [
            staging / "extracted/homes/alice/.ssh/authorized_keys",
            staging / "extracted/sudoers.d/bastion-users",
            staging / "extracted/ssh/sshd_config.d/bastion.conf",
        ]
        before = {str(path): _sha256_file(path) for path in tracked}
        manifest = _repair_tenant(staging, "helix", "fix3.json")
        after = {str(path): _sha256_file(path) for path in tracked}
        assert manifest["noop"] is True
        assert before == after

    def test_vertex_fourth_repair_still_noop(self) -> None:
        """Fourth vertex repair remains noop."""
        staging = _fresh_staging("seq_vertex_fourth")
        for index in range(1, 4):
            _repair_tenant(staging, "vertex", f"fix{index}.json")
        manifest = _repair_tenant(staging, "vertex", "fix4.json")
        assert manifest["noop"] is True

    def test_vertex_first_and_second_manifest_hashes_differ_then_stable(self) -> None:
        """Vertex first repair manifest hash differs from second noop digest."""
        staging = _fresh_staging("seq_vertex_hash")
        first = _repair_tenant(staging, "vertex", "fix1.json")
        second = _repair_tenant(staging, "vertex", "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])

    def test_vertex_triple_repair_idempotent_on_disk(self) -> None:
        """Third vertex repair leaves tracked staging file digests unchanged."""
        staging = _fresh_staging("seq_vertex_triple")
        _repair_tenant(staging, "vertex", "fix1.json")
        _repair_tenant(staging, "vertex", "fix2.json")
        tracked = [
            staging / "extracted/homes/alice/.ssh/authorized_keys",
            staging / "extracted/sudoers.d/bastion-users",
            staging / "extracted/ssh/sshd_config.d/bastion.conf",
        ]
        before = {str(path): _sha256_file(path) for path in tracked}
        manifest = _repair_tenant(staging, "vertex", "fix3.json")
        after = {str(path): _sha256_file(path) for path in tracked}
        assert manifest["noop"] is True
        assert before == after

    def test_continuum_fourth_repair_still_noop(self) -> None:
        """Fourth continuum repair remains noop."""
        staging = _fresh_staging("seq_continuum_fourth")
        for index in range(1, 4):
            _repair_tenant(staging, "continuum", f"fix{index}.json")
        manifest = _repair_tenant(staging, "continuum", "fix4.json")
        assert manifest["noop"] is True

    def test_continuum_first_and_second_manifest_hashes_differ_then_stable(self) -> None:
        """Continuum first repair manifest hash differs from second noop digest."""
        staging = _fresh_staging("seq_continuum_hash")
        first = _repair_tenant(staging, "continuum", "fix1.json")
        second = _repair_tenant(staging, "continuum", "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])

    def test_continuum_triple_repair_idempotent_on_disk(self) -> None:
        """Third continuum repair leaves tracked staging file digests unchanged."""
        staging = _fresh_staging("seq_continuum_triple")
        _repair_tenant(staging, "continuum", "fix1.json")
        _repair_tenant(staging, "continuum", "fix2.json")
        tracked = [
            staging / "extracted/homes/alice/.ssh/authorized_keys",
            staging / "extracted/sudoers.d/bastion-users",
            staging / "extracted/ssh/sshd_config.d/bastion.conf",
        ]
        before = {str(path): _sha256_file(path) for path in tracked}
        manifest = _repair_tenant(staging, "continuum", "fix3.json")
        after = {str(path): _sha256_file(path) for path in tracked}
        assert manifest["noop"] is True
        assert before == after


class TestAuditReportContract:

    def test_aurora_audit_report_has_required_fields(self) -> None:
        """Aurora audit report includes staging_root tenant violations and clean."""
        staging = _fresh_staging("contract_aurora")
        report = _audit_tenant(staging, "aurora", "audit_aurora_contract.json")
        assert set(report) == {"staging_root", "tenant", "violations", "clean"}
        assert isinstance(report["violations"], list)

    def test_aurora_post_repair_audit_violations_empty(self) -> None:
        """Post-repair aurora audit violations list is empty."""
        staging = _fresh_staging("contract_aurora_post")
        _repair_tenant(staging, "aurora")
        report = _audit_tenant(staging, "aurora", "audit_aurora_post.json")
        assert report["violations"] == []
        assert report["clean"] is True

    def test_helix_audit_report_has_required_fields(self) -> None:
        """Helix audit report includes staging_root tenant violations and clean."""
        staging = _fresh_staging("contract_helix")
        report = _audit_tenant(staging, "helix", "audit_helix_contract.json")
        assert set(report) == {"staging_root", "tenant", "violations", "clean"}
        assert isinstance(report["violations"], list)

    def test_helix_post_repair_audit_violations_empty(self) -> None:
        """Post-repair helix audit violations list is empty."""
        staging = _fresh_staging("contract_helix_post")
        _repair_tenant(staging, "helix")
        report = _audit_tenant(staging, "helix", "audit_helix_post.json")
        assert report["violations"] == []
        assert report["clean"] is True

    def test_vertex_audit_report_has_required_fields(self) -> None:
        """Vertex audit report includes staging_root tenant violations and clean."""
        staging = _fresh_staging("contract_vertex")
        report = _audit_tenant(staging, "vertex", "audit_vertex_contract.json")
        assert set(report) == {"staging_root", "tenant", "violations", "clean"}
        assert isinstance(report["violations"], list)

    def test_vertex_post_repair_audit_violations_empty(self) -> None:
        """Post-repair vertex audit violations list is empty."""
        staging = _fresh_staging("contract_vertex_post")
        _repair_tenant(staging, "vertex")
        report = _audit_tenant(staging, "vertex", "audit_vertex_post.json")
        assert report["violations"] == []
        assert report["clean"] is True

    def test_continuum_audit_report_has_required_fields(self) -> None:
        """Continuum audit report includes staging_root tenant violations and clean."""
        staging = _fresh_staging("contract_continuum")
        report = _audit_tenant(staging, "continuum", "audit_continuum_contract.json")
        assert set(report) == {"staging_root", "tenant", "violations", "clean"}
        assert isinstance(report["violations"], list)

    def test_continuum_post_repair_audit_violations_empty(self) -> None:
        """Post-repair continuum audit violations list is empty."""
        staging = _fresh_staging("contract_continuum_post")
        _repair_tenant(staging, "continuum")
        report = _audit_tenant(staging, "continuum", "audit_continuum_post.json")
        assert report["violations"] == []
        assert report["clean"] is True


def _redis_hset(key: str, field: str, value: str) -> None:
    subprocess.run(
        ["redis-cli", "HSET", key, field, value],
        check=True,
    )


def _path_mode_bits(path: Path) -> int:
    return path.stat().st_mode & 0o777


MODE_ONLY_DIRECTORY_PATHS = frozenset(
    {
        "homes/alice/.ssh",
        "homes/bob/.ssh",
    }
)


def _assert_manifest_excludes_mode_only_directories(manifest: dict) -> None:
    change_paths = {change["path"] for change in manifest["changes"]}
    overlap = change_paths & MODE_ONLY_DIRECTORY_PATHS
    assert not overlap, f"mode-only directories must not appear in changes: {sorted(overlap)}"
    for change in manifest["changes"]:
        assert change["before_sha256"] != change["after_sha256"]


class TestManifestModeExclusion:
    def test_prod_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Prod repair manifest lists content rewrites only, not ssh directory paths."""
        staging = _fresh_staging("mode_excl_prod")
        manifest = _repair_tenant(staging, "prod")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_nexus_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Nexus repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_nexus")
        manifest = _repair_tenant(staging, "nexus")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_rift_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Rift repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_rift")
        manifest = _repair_tenant(staging, "rift")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_prism_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Prism repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_prism")
        manifest = _repair_tenant(staging, "prism")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_quasar_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Quasar repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_quasar")
        manifest = _repair_tenant(staging, "quasar")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_atlas_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Atlas repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_atlas")
        manifest = _repair_tenant(staging, "atlas")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_aurora_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Aurora repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_aurora")
        manifest = _repair_tenant(staging, "aurora")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_helix_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Helix repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_helix")
        manifest = _repair_tenant(staging, "helix")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_vertex_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Vertex repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_vertex")
        manifest = _repair_tenant(staging, "vertex")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_continuum_repair_excludes_ssh_directory_paths_from_changes(self) -> None:
        """Continuum repair manifest omits mode-only directory paths from changes."""
        staging = _fresh_staging("mode_excl_continuum")
        manifest = _repair_tenant(staging, "continuum")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_repair_restores_bob_ssh_directory_mode(self) -> None:
        """Repair applies registry file_modes to bob .ssh directory."""
        staging = _fresh_staging("mode_bob_dir")
        _repair_tenant(staging, "prod")
        mode = oct(
            (staging / "extracted/homes/bob/.ssh").stat().st_mode & 0o777
        )[2:]
        assert mode in {"700", "0700"}

    def test_mode_manifest_desk_is_decoy(self) -> None:
        """Mode manifest desk exists but repair excludes directory-only chmod paths."""
        desk = Path("/app/docs/mode_manifest_desk.md")
        assert desk.is_file()
        assert "include_mode_only_directories" in desk.read_text(encoding="utf-8")
        staging = _fresh_staging("desk_mode_manifest")
        manifest = _repair_tenant(staging, "prod")
        _assert_manifest_excludes_mode_only_directories(manifest)

    def test_handbook_amendment_2025_10_content_rewrite_scope(self) -> None:
        """Handbook Amendment 2025-10 defines content_rewrite_only manifest scope."""
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(encoding="utf-8")
        assert "Amendment 2025-10" in handbook
        assert "MANIFEST_CHANGES_SCOPE=content_rewrite_only" in handbook
        assert "Mode-only directory repairs" in handbook


ALL_TENANTS = [
    "prod",
    "staging",
    "canary",
    "dr",
    "edge",
    "vault",
    "atlas",
    "comet",
    "orbit",
    "pulse",
    "nexus",
    "rift",
    "prism",
    "quasar",
    "aurora",
    "helix",
    "vertex",
    "continuum",
    "eclipse",
    "nebula",
    "solstice",
    "pulsar",
    "zenith",
    "lumen",
    "cobalt",
    "vector",
    "horizon",
    "flux",
    "apex",
    "relay",
    "spire",
    "nova",
    "titan",
    "forge",
    "ember",
    "onyx",
    "sentinel",
    "cipher",
    "quartz",
    "obsidian",
    "garnet",
    "slate",
    "crimson",
    "jade",
    "opal",
    "ivory",
]

NEW_HELD_OUT_TENANTS = ["eclipse", "nebula", "solstice", "pulsar"]

NEW_TENANT_OVERLAY_MARKERS = {
    "eclipse": "UsePAM yes",
    "nebula": "TCPKeepAlive yes",
    "solstice": "PermitUserEnvironment no",
    "pulsar": "GatewayPorts no",
}

NEW_TENANT_CACHE_TRAPS = {
    "eclipse": "UsePAM no",
    "nebula": "TCPKeepAlive no",
    "solstice": "PermitUserEnvironment yes",
    "pulsar": "GatewayPorts yes",
}


def _assert_violations_sorted(violations: list[dict]) -> None:
    ordered = sorted(violations, key=lambda item: (item["path"], item["kind"]))
    assert violations == ordered


class TestTenantManifestSweepRoundH:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_repair_excludes_ssh_directory_paths_from_changes(self, tenant: str) -> None:
        """Every tenant repair manifest omits mode-only ssh directory paths."""
        staging = _fresh_staging(f"sweep_mode_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        _assert_manifest_excludes_mode_only_directories(manifest)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_digest_matches_sorted_changes(self, tenant: str) -> None:
        """Every tenant manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging(f"sweep_digest_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["changes"] == sorted(manifest["changes"], key=lambda item: item["path"])
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_second_repair_is_noop(self, tenant: str) -> None:
        """Second repair on every tenant staging tree is noop."""
        staging = _fresh_staging(f"sweep_noop_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["noop"] is True
        assert manifest["changes"] == []

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_audit_is_clean(self, tenant: str) -> None:
        """Post-repair audit is clean for every tenant overlay."""
        staging = _fresh_staging(f"sweep_clean_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["tenant"] == tenant
        assert report["clean"] is True
        assert report["violations"] == []

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_violations_sorted_by_path_then_kind(self, tenant: str) -> None:
        """Pre-repair audit violations are sorted by path then kind for every tenant."""
        staging = _fresh_staging(f"sweep_sort_{tenant}")
        report = _audit_tenant(staging, tenant)
        _assert_violations_sorted(report["violations"])


class TestHeldOutEclipseTenant:
    def test_eclipse_overlay_applied(self) -> None:
        """Held-out eclipse tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("eclipse_overlay")
        manifest = _repair_tenant(staging, "eclipse", "fix_eclipse.json")
        assert manifest["tenant"] == "eclipse"
        assert "UsePAM yes" in _sshd_conf(staging)
        assert "PrintMotd no" in _sshd_conf(staging)

    def test_eclipse_ignores_seeded_registry_cache(self) -> None:
        """Eclipse repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("eclipse_cache")
        _repair_tenant(staging, "eclipse")
        conf = _sshd_conf(staging)
        assert "UsePAM yes" in conf
        assert "UsePAM no" not in conf

    def test_eclipse_tenant_audit_clean_after_repair(self) -> None:
        """Eclipse repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("eclipse_clean")
        _repair_tenant(staging, "eclipse")
        report = _audit_tenant(staging, "eclipse", "audit_eclipse.json")
        assert report["tenant"] == "eclipse"
        assert report["staging_root"].endswith("/extracted")
        assert report["clean"] is True

    def test_eclipse_manifest_digest_matches_sorted_changes(self) -> None:
        """Eclipse manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("eclipse_manifest")
        manifest = _repair_tenant(staging, "eclipse")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_eclipse_second_repair_noop_preserves_files(self) -> None:
        """Second eclipse repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("eclipse_noop")
        _repair_tenant(staging, "eclipse", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "eclipse", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutNebulaTenant:
    def test_nebula_overlay_applied(self) -> None:
        """Held-out nebula tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("nebula_overlay")
        manifest = _repair_tenant(staging, "nebula", "fix_nebula.json")
        assert manifest["tenant"] == "nebula"
        assert "TCPKeepAlive yes" in _sshd_conf(staging)
        assert "UseDNS no" in _sshd_conf(staging)

    def test_nebula_ignores_seeded_registry_cache(self) -> None:
        """Nebula repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("nebula_cache")
        _repair_tenant(staging, "nebula")
        conf = _sshd_conf(staging)
        assert "TCPKeepAlive yes" in conf
        assert "TCPKeepAlive no" not in conf

    def test_nebula_tenant_audit_clean_after_repair(self) -> None:
        """Nebula repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("nebula_clean")
        _repair_tenant(staging, "nebula")
        report = _audit_tenant(staging, "nebula", "audit_nebula.json")
        assert report["tenant"] == "nebula"
        assert report["clean"] is True

    def test_nebula_manifest_digest_matches_sorted_changes(self) -> None:
        """Nebula manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("nebula_manifest")
        manifest = _repair_tenant(staging, "nebula")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_nebula_second_repair_noop_preserves_files(self) -> None:
        """Second nebula repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("nebula_noop")
        _repair_tenant(staging, "nebula", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "nebula", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutSolsticeTenant:
    def test_solstice_overlay_applied(self) -> None:
        """Held-out solstice tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("solstice_overlay")
        manifest = _repair_tenant(staging, "solstice", "fix_solstice.json")
        assert manifest["tenant"] == "solstice"
        assert "PermitUserEnvironment no" in _sshd_conf(staging)
        assert "MaxStartups 10:30:60" in _sshd_conf(staging)

    def test_solstice_ignores_seeded_registry_cache(self) -> None:
        """Solstice repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("solstice_cache")
        _repair_tenant(staging, "solstice")
        conf = _sshd_conf(staging)
        assert "PermitUserEnvironment no" in conf
        assert "PermitUserEnvironment yes" not in conf

    def test_solstice_tenant_audit_clean_after_repair(self) -> None:
        """Solstice repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("solstice_clean")
        _repair_tenant(staging, "solstice")
        report = _audit_tenant(staging, "solstice", "audit_solstice.json")
        assert report["tenant"] == "solstice"
        assert report["clean"] is True

    def test_solstice_manifest_digest_matches_sorted_changes(self) -> None:
        """Solstice manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("solstice_manifest")
        manifest = _repair_tenant(staging, "solstice")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_solstice_second_repair_noop_preserves_files(self) -> None:
        """Second solstice repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("solstice_noop")
        _repair_tenant(staging, "solstice", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "solstice", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutPulsarTenant:
    def test_pulsar_overlay_applied(self) -> None:
        """Held-out pulsar tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("pulsar_overlay")
        manifest = _repair_tenant(staging, "pulsar", "fix_pulsar.json")
        assert manifest["tenant"] == "pulsar"
        assert "GatewayPorts no" in _sshd_conf(staging)
        assert "PermitTunnel no" in _sshd_conf(staging)

    def test_pulsar_ignores_seeded_registry_cache(self) -> None:
        """Pulsar repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("pulsar_cache")
        _repair_tenant(staging, "pulsar")
        conf = _sshd_conf(staging)
        assert "GatewayPorts no" in conf
        assert "GatewayPorts yes" not in conf

    def test_pulsar_tenant_audit_clean_after_repair(self) -> None:
        """Pulsar repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("pulsar_clean")
        _repair_tenant(staging, "pulsar")
        report = _audit_tenant(staging, "pulsar", "audit_pulsar.json")
        assert report["tenant"] == "pulsar"
        assert report["clean"] is True

    def test_pulsar_manifest_digest_matches_sorted_changes(self) -> None:
        """Pulsar manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("pulsar_manifest")
        manifest = _repair_tenant(staging, "pulsar")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_pulsar_second_repair_noop_preserves_files(self) -> None:
        """Second pulsar repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("pulsar_noop")
        _repair_tenant(staging, "pulsar", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "pulsar", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestDeepHardeningRoundH:
    def test_eclipse_and_aurora_repairs_remain_distinct(self) -> None:
        """Eclipse and aurora sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundh_eclipse")
        b = _fresh_staging("roundh_aurora")
        _repair_tenant(a, "eclipse")
        _repair_tenant(b, "aurora")
        assert "UsePAM yes" in _sshd_conf(a)
        assert "AddressFamily inet" in _sshd_conf(b)
        assert "AddressFamily inet" not in _sshd_conf(a)

    def test_nebula_and_helix_repairs_remain_distinct(self) -> None:
        """Nebula and helix sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundh_nebula")
        b = _fresh_staging("roundh_helix")
        _repair_tenant(a, "nebula")
        _repair_tenant(b, "helix")
        assert "TCPKeepAlive yes" in _sshd_conf(a)
        assert "HostbasedAuthentication no" in _sshd_conf(b)
        assert "HostbasedAuthentication no" not in _sshd_conf(a)

    def test_solstice_and_vertex_repairs_remain_distinct(self) -> None:
        """Solstice and vertex sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundh_solstice")
        b = _fresh_staging("roundh_vertex")
        _repair_tenant(a, "solstice")
        _repair_tenant(b, "vertex")
        assert "PermitUserEnvironment no" in _sshd_conf(a)
        assert "PermitEmptyPasswords no" in _sshd_conf(b)
        assert "PermitEmptyPasswords no" not in _sshd_conf(a)

    def test_pulsar_and_continuum_repairs_remain_distinct(self) -> None:
        """Pulsar and continuum sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundh_pulsar")
        b = _fresh_staging("roundh_continuum")
        _repair_tenant(a, "pulsar")
        _repair_tenant(b, "continuum")
        assert "GatewayPorts no" in _sshd_conf(a)
        assert "StreamLocalBindMask 077" in _sshd_conf(b)
        assert "StreamLocalBindMask 077" not in _sshd_conf(a)

    def test_eclipse_and_nexus_audit_clean_independently(self) -> None:
        """Eclipse and nexus each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundh_audit_eclipse")
        b = _fresh_staging("roundh_audit_nexus")
        _repair_tenant(a, "eclipse")
        _repair_tenant(b, "nexus")
        assert _audit_tenant(a, "eclipse")["clean"] is True
        assert _audit_tenant(b, "nexus")["clean"] is True

    def test_nebula_and_rift_audit_clean_independently(self) -> None:
        """Nebula and rift each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundh_audit_nebula")
        b = _fresh_staging("roundh_audit_rift")
        _repair_tenant(a, "nebula")
        _repair_tenant(b, "rift")
        assert _audit_tenant(a, "nebula")["clean"] is True
        assert _audit_tenant(b, "rift")["clean"] is True

    def test_solstice_and_prism_audit_clean_independently(self) -> None:
        """Solstice and prism each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundh_audit_solstice")
        b = _fresh_staging("roundh_audit_prism")
        _repair_tenant(a, "solstice")
        _repair_tenant(b, "prism")
        assert _audit_tenant(a, "solstice")["clean"] is True
        assert _audit_tenant(b, "prism")["clean"] is True

    def test_pulsar_and_quasar_audit_clean_independently(self) -> None:
        """Pulsar and quasar each audit clean after tenant-scoped repair."""
        a = _fresh_staging("roundh_audit_pulsar")
        b = _fresh_staging("roundh_audit_quasar")
        _repair_tenant(a, "pulsar")
        _repair_tenant(b, "quasar")
        assert _audit_tenant(a, "pulsar")["clean"] is True
        assert _audit_tenant(b, "quasar")["clean"] is True

    def test_eclipse_and_prod_manifests_use_distinct_tenants(self) -> None:
        """Eclipse and prod manifests record their respective tenant ids."""
        a = _fresh_staging("roundh_iso_eclipse")
        b = _fresh_staging("roundh_iso_prod")
        ma = _repair_tenant(a, "eclipse")
        mb = _repair_tenant(b, "prod")
        assert ma["tenant"] == "eclipse"
        assert mb["tenant"] == "prod"
        assert ma["manifest_sha256"] != mb["manifest_sha256"]

    def test_nebula_and_staging_manifests_use_distinct_tenants(self) -> None:
        """Nebula and staging manifests record their respective tenant ids."""
        a = _fresh_staging("roundh_iso_nebula")
        b = _fresh_staging("roundh_iso_staging")
        ma = _repair_tenant(a, "nebula")
        mb = _repair_tenant(b, "staging")
        assert ma["tenant"] == "nebula"
        assert mb["tenant"] == "staging"

    def test_solstice_and_canary_manifests_use_distinct_tenants(self) -> None:
        """Solstice and canary manifests record their respective tenant ids."""
        a = _fresh_staging("roundh_iso_solstice")
        b = _fresh_staging("roundh_iso_canary")
        ma = _repair_tenant(a, "solstice")
        mb = _repair_tenant(b, "canary")
        assert ma["tenant"] == "solstice"
        assert mb["tenant"] == "canary"

    def test_pulsar_and_dr_manifests_use_distinct_tenants(self) -> None:
        """Pulsar and dr manifests record their respective tenant ids."""
        a = _fresh_staging("roundh_iso_pulsar")
        b = _fresh_staging("roundh_iso_dr")
        ma = _repair_tenant(a, "pulsar")
        mb = _repair_tenant(b, "dr")
        assert ma["tenant"] == "pulsar"
        assert mb["tenant"] == "dr"


class TestDeepHardeningRoundI:
    @pytest.mark.parametrize(
        "tenant,marker",
        [
            ("eclipse", "UsePAM yes"),
            ("nebula", "TCPKeepAlive yes"),
            ("solstice", "PermitUserEnvironment no"),
            ("pulsar", "GatewayPorts no"),
        ],
    )
    def test_new_tenant_overlay_marker_present(self, tenant: str, marker: str) -> None:
        """New held-out tenant overlay markers appear after repair."""
        staging = _fresh_staging(f"roundi_overlay_{tenant}")
        _repair_tenant(staging, tenant)
        assert marker in _sshd_conf(staging)

    @pytest.mark.parametrize(
        "tenant,trap",
        [
            ("eclipse", "UsePAM no"),
            ("nebula", "TCPKeepAlive no"),
            ("solstice", "PermitUserEnvironment yes"),
            ("pulsar", "GatewayPorts yes"),
        ],
    )
    def test_new_tenant_ignores_registry_cache_trap(self, tenant: str, trap: str) -> None:
        """New held-out tenants ignore stale registry cache sshd traps."""
        staging = _fresh_staging(f"roundi_cache_{tenant}")
        _repair_tenant(staging, tenant)
        assert trap not in _sshd_conf(staging)

    @pytest.mark.parametrize("tenant", NEW_HELD_OUT_TENANTS)
    def test_new_tenant_manifest_excludes_mode_only_directories(self, tenant: str) -> None:
        """New held-out tenant manifests exclude mode-only directory paths."""
        staging = _fresh_staging(f"roundi_mode_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        _assert_manifest_excludes_mode_only_directories(manifest)

    @pytest.mark.parametrize("tenant", NEW_HELD_OUT_TENANTS)
    def test_new_tenant_pre_repair_not_clean(self, tenant: str) -> None:
        """Pre-repair audit is not clean for new held-out tenants."""
        staging = _fresh_staging(f"roundi_preclean_{tenant}")
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is False
        assert report["violations"]


class TestDeskTrapBehavioralRound4:
    def test_eclipse_cache_desk_is_decoy(self) -> None:
        """Eclipse cache desk exists but repair follows live overlay not cache."""
        desk = Path("/app/docs/eclipse_cache_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_eclipse")
        _repair_tenant(staging, "eclipse")
        assert "UsePAM yes" in _sshd_conf(staging)

    def test_nebula_alias_desk_is_decoy(self) -> None:
        """Nebula alias desk exists but repair uses nebula tenant overlay not staging."""
        desk = Path("/app/docs/nebula_alias_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_nebula")
        _repair_tenant(staging, "nebula")
        assert "TCPKeepAlive yes" in _sshd_conf(staging)

    def test_solstice_global_first_desk_is_decoy(self) -> None:
        """Solstice global-first desk exists but tenant overlay leaves win."""
        desk = Path("/app/docs/solstice_global_first_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_solstice")
        _repair_tenant(staging, "solstice")
        assert "PermitUserEnvironment no" in _sshd_conf(staging)

    def test_pulsar_snapshot_desk_is_decoy(self) -> None:
        """Pulsar snapshot desk exists but repair uses live registry not archive snapshot."""
        desk = Path("/app/docs/pulsar_snapshot_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_pulsar")
        _repair_tenant(staging, "pulsar")
        assert "GatewayPorts no" in _sshd_conf(staging)


class TestCrossTenantIsolationRound4:
    @pytest.mark.parametrize(
        "left,right,left_marker,right_marker",
        [
            ("eclipse", "nexus", "UsePAM yes", "ClientAliveInterval 120"),
            ("nebula", "rift", "TCPKeepAlive yes", "MaxSessions 4"),
            ("solstice", "prism", "PermitUserEnvironment no", "LogLevel VERBOSE"),
            ("pulsar", "quasar", "GatewayPorts no", "PermitTTY no"),
            ("eclipse", "atlas", "UsePAM yes", "Compression yes"),
            ("nebula", "comet", "TCPKeepAlive yes", "Banner /etc/issue.net"),
            ("solstice", "orbit", "PermitUserEnvironment no", "StrictModes yes"),
            ("pulsar", "pulse", "GatewayPorts no", "KexAlgorithms curve25519-sha256"),
        ],
    )
    def test_new_and_legacy_tenant_sshd_directives_differ(
        self, left: str, right: str, left_marker: str, right_marker: str
    ) -> None:
        """New held-out tenants remain isolated from legacy tenant sshd exports."""
        a = _fresh_staging(f"iso4_{left}")
        b = _fresh_staging(f"iso4_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert left_marker in _sshd_conf(a)
        assert right_marker in _sshd_conf(b)
        assert right_marker not in _sshd_conf(a)


class TestRepairSequenceDepthRound2:
    @pytest.mark.parametrize("tenant", NEW_HELD_OUT_TENANTS)
    def test_third_repair_still_noop(self, tenant: str) -> None:
        """Third repair on new held-out tenant staging remains noop."""
        staging = _fresh_staging(f"seq2_{tenant}_third")
        for index in range(1, 3):
            _repair_tenant(staging, tenant, f"fix{index}.json")
        manifest = _repair_tenant(staging, tenant, "fix3.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", NEW_HELD_OUT_TENANTS)
    def test_first_and_second_manifest_hashes_differ_then_stable(self, tenant: str) -> None:
        """First repair manifest hash differs from second noop digest for new tenants."""
        staging = _fresh_staging(f"seq2_{tenant}_hash")
        first = _repair_tenant(staging, tenant, "fix1.json")
        second = _repair_tenant(staging, tenant, "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])


class TestTenantChangeDigestSweepRoundI:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_change_after_digests_match_on_disk(self, tenant: str) -> None:
        """Every manifest change after_sha256 matches repaired on-disk file bytes."""
        staging = _fresh_staging(f"sweep_disk_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)


class TestTenantPreRepairAuditSweepRoundI:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_audit_not_clean(self, tenant: str) -> None:
        """Pre-repair audit reports drift for every tenant bundle."""
        staging = _fresh_staging(f"sweep_preclean_{tenant}")
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is False
        assert report["violations"]


class TestTenantStagingRootSweepRoundI:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_repair_manifest_staging_root_absolute(self, tenant: str) -> None:
        """Repair manifest staging_root is absolute extracted path for every tenant."""
        staging = _fresh_staging(f"sweep_root_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["staging_root"].startswith("/")
        assert manifest["staging_root"].endswith("/extracted")


ROUND3_HELD_OUT_TENANTS = ["zenith", "lumen", "cobalt", "vector"]

ROUND3_TENANT_OVERLAY_MARKERS = {
    "zenith": "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u",
    "lumen": "ChallengeResponseAuthentication no",
    "cobalt": "GSSAPIAuthentication no",
    "vector": "HostKeyAlgorithms ssh-ed25519",
}

ROUND3_TENANT_CACHE_TRAPS = {
            "zenith": "AllowUsers eve",
    "lumen": "ChallengeResponseAuthentication yes",
    "cobalt": "GSSAPIAuthentication yes",
    "vector": "HostKeyAlgorithms ssh-rsa",
}

PRE_REPAIR_VIOLATION_KINDS = frozenset(
    {
        "ssh_key_mismatch",
        "mode_mismatch",
        "sshd_setting",
        "sudoers_missing",
        "sudoers_unauthorized",
    }
)


class TestTenantBehavioralSweepRoundJ:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_tenant_matches_cli_flag(self, tenant: str) -> None:
        """Repair manifest tenant field matches --tenant for every overlay."""
        staging = _fresh_staging(f"rj_tenant_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["tenant"] == tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_changes_sorted_by_path(self, tenant: str) -> None:
        """Repair manifest changes are sorted by ascending path for every tenant."""
        staging = _fresh_staging(f"rj_sort_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        paths = [change["path"] for change in manifest["changes"]]
        assert paths == sorted(paths)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_digest_is_64_char_hex(self, tenant: str) -> None:
        """manifest_sha256 is 64-char lowercase hex for every tenant repair."""
        staging = _fresh_staging(f"rj_hex_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        digest = manifest["manifest_sha256"]
        assert len(digest) == 64
        assert digest == digest.lower()
        assert all(ch in "0123456789abcdef" for ch in digest)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_second_repair_noop_true(self, tenant: str) -> None:
        """Second repair noop flag is true for every tenant staging tree."""
        staging = _fresh_staging(f"rj_noop_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_second_repair_empty_changes(self, tenant: str) -> None:
        """Second repair emits empty changes for every tenant."""
        staging = _fresh_staging(f"rj_empty_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["changes"] == []

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_audit_clean_true(self, tenant: str) -> None:
        """Post-repair audit clean flag is true for every tenant."""
        staging = _fresh_staging(f"rj_clean_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is True

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_zero_violations(self, tenant: str) -> None:
        """Post-repair audit violations list is empty for every tenant."""
        staging = _fresh_staging(f"rj_zero_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["violations"] == []

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_audit_not_clean(self, tenant: str) -> None:
        """Pre-repair audit reports drift for every tenant bundle."""
        staging = _fresh_staging(f"rj_preclean_{tenant}")
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is False

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_violations_list(self, tenant: str) -> None:
        """Pre-repair audit emits non-empty violations for every tenant."""
        staging = _fresh_staging(f"rj_previol_{tenant}")
        report = _audit_tenant(staging, tenant)
        assert report["violations"]

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_staging_root_ends_with_extracted(self, tenant: str) -> None:
        """Repair manifest staging_root ends with /extracted for every tenant."""
        staging = _fresh_staging(f"rj_root_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["staging_root"].endswith("/extracted")

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_staging_root_is_absolute_path(self, tenant: str) -> None:
        """Repair manifest staging_root is absolute for every tenant."""
        staging = _fresh_staging(f"rj_abs_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["staging_root"].startswith("/")

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_first_repair_noop_false(self, tenant: str) -> None:
        """First repair on drifted bundle is not noop for every tenant."""
        staging = _fresh_staging(f"rj_first_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["noop"] is False


class TestTenantBehavioralSweepRoundK:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_change_paths_not_absolute(self, tenant: str) -> None:
        """Manifest change paths are relative to extracted root for every tenant."""
        staging = _fresh_staging(f"rk_rel_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            assert not change["path"].startswith("/")

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_change_before_sha256_is_hex(self, tenant: str) -> None:
        """Every change before_sha256 is 64-char hex for every tenant."""
        staging = _fresh_staging(f"rk_before_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            assert len(change["before_sha256"]) == 64

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_change_after_sha256_is_hex(self, tenant: str) -> None:
        """Every change after_sha256 is 64-char hex for every tenant."""
        staging = _fresh_staging(f"rk_after_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            assert len(change["after_sha256"]) == 64

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_changes_before_after_differ(self, tenant: str) -> None:
        """Listed changes have distinct before and after digests for every tenant."""
        staging = _fresh_staging(f"rk_diff_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            assert change["before_sha256"] != change["after_sha256"]

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_excludes_mode_only_ssh_dirs(self, tenant: str) -> None:
        """Every tenant repair manifest excludes mode-only ssh directory paths."""
        staging = _fresh_staging(f"rk_mode_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        _assert_manifest_excludes_mode_only_directories(manifest)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_audit_tenant_field_matches(self, tenant: str) -> None:
        """Post-repair audit tenant field matches --tenant for every overlay."""
        staging = _fresh_staging(f"rk_audit_t_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["tenant"] == tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_audit_staging_root_matches_repair(self, tenant: str) -> None:
        """Audit staging_root matches repair staging_root for every tenant."""
        staging = _fresh_staging(f"rk_rootmatch_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["staging_root"] == manifest["staging_root"]

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_audit_violations_sorted(self, tenant: str) -> None:
        """Pre-repair audit violations sorted by path then kind for every tenant."""
        staging = _fresh_staging(f"rk_vsort_{tenant}")
        report = _audit_tenant(staging, tenant)
        _assert_violations_sorted(report["violations"])

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_third_repair_still_noop(self, tenant: str) -> None:
        """Third repair remains noop for every tenant staging tree."""
        staging = _fresh_staging(f"rk_third_{tenant}")
        for index in range(1, 3):
            _repair_tenant(staging, tenant, f"fix{index}.json")
        manifest = _repair_tenant(staging, tenant, "fix3.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_first_manifest_has_changes(self, tenant: str) -> None:
        """First repair on drifted bundle lists content changes for every tenant."""
        staging = _fresh_staging(f"rk_changes_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["changes"]

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_noop_manifest_hash_matches_empty_array(self, tenant: str) -> None:
        """Second repair manifest_sha256 matches empty sorted changes digest."""
        staging = _fresh_staging(f"rk_nhash_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["manifest_sha256"] == _manifest_hash([])

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_noop_manifest_not_full_object_hash(self, tenant: str) -> None:
        """Noop manifest_sha256 is not the desk-style full-object digest."""
        staging = _fresh_staging(f"rk_nfull_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)


class TestTenantBehavioralSweepRoundL:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_ssh_key_mismatch(self, tenant: str) -> None:
        """Pre-repair audit includes ssh_key_mismatch for every tenant."""
        staging = _fresh_staging(f"rl_ssh_{tenant}")
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "ssh_key_mismatch" in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_mode_mismatch(self, tenant: str) -> None:
        """Pre-repair audit includes mode_mismatch for every tenant."""
        staging = _fresh_staging(f"rl_mode_{tenant}")
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "mode_mismatch" in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_sshd_setting(self, tenant: str) -> None:
        """Pre-repair audit includes sshd_setting for every tenant."""
        staging = _fresh_staging(f"rl_sshd_{tenant}")
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "sshd_setting" in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_sudoers_missing(self, tenant: str) -> None:
        """Pre-repair audit includes sudoers_missing for every tenant."""
        staging = _fresh_staging(f"rl_sudo_{tenant}")
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "sudoers_missing" in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_sudoers_unauthorized(self, tenant: str) -> None:
        """Pre-repair audit includes sudoers_unauthorized for every tenant."""
        staging = _fresh_staging(f"rl_unauth_{tenant}")
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "sudoers_unauthorized" in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_kinds_subset_of_expected(self, tenant: str) -> None:
        """Pre-repair violation kinds stay within expected audit taxonomy."""
        staging = _fresh_staging(f"rl_kinds_{tenant}")
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert kinds.issubset(PRE_REPAIR_VIOLATION_KINDS)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_no_ssh_key_mismatch(self, tenant: str) -> None:
        """Post-repair audit has no ssh_key_mismatch for every tenant."""
        staging = _fresh_staging(f"rl_postssh_{tenant}")
        _repair_tenant(staging, tenant)
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "ssh_key_mismatch" not in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_no_mode_mismatch(self, tenant: str) -> None:
        """Post-repair audit has no mode_mismatch for every tenant."""
        staging = _fresh_staging(f"rl_postmode_{tenant}")
        _repair_tenant(staging, tenant)
        kinds = {v["kind"] for v in _audit_tenant(staging, tenant)["violations"]}
        assert "mode_mismatch" not in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_change_after_matches_disk(self, tenant: str) -> None:
        """Every manifest after_sha256 matches on-disk bytes for every tenant."""
        staging = _fresh_staging(f"rl_disk_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            target = staging / "extracted" / change["path"]
            assert change["after_sha256"] == _sha256_file(target)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_digest_matches_sorted_changes(self, tenant: str) -> None:
        """manifest_sha256 matches compact sorted changes digest for every tenant."""
        staging = _fresh_staging(f"rl_digest_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_digest_not_full_object(self, tenant: str) -> None:
        """manifest_sha256 is not the desk full-manifest object digest."""
        staging = _fresh_staging(f"rl_full_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["manifest_sha256"] != _wrong_full_manifest_hash(manifest)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_audit_staging_root_absolute(self, tenant: str) -> None:
        """Pre-repair audit staging_root is absolute for every tenant."""
        staging = _fresh_staging(f"rl_aroot_{tenant}")
        report = _audit_tenant(staging, tenant)
        assert report["staging_root"].startswith("/")

class TestHeldOutZenithTenant:
    def test_zenith_overlay_applied(self) -> None:
        """Held-out zenith tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("zenith_overlay")
        manifest = _repair_tenant(staging, "zenith", "fix_zenith.json")
        assert manifest["tenant"] == "zenith"
        assert "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u" in _sshd_conf(staging)

    def test_zenith_ignores_seeded_registry_cache(self) -> None:
        """Zenith repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("zenith_cache")
        _repair_tenant(staging, "zenith")
        conf = _sshd_conf(staging)
        assert "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u" in conf
        assert "AllowUsers eve" not in conf

    def test_zenith_tenant_audit_clean_after_repair(self) -> None:
        """Zenith repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("zenith_clean")
        _repair_tenant(staging, "zenith")
        report = _audit_tenant(staging, "zenith", "audit_zenith.json")
        assert report["tenant"] == "zenith"
        assert report["clean"] is True

    def test_zenith_manifest_digest_matches_sorted_changes(self) -> None:
        """Zenith manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("zenith_manifest")
        manifest = _repair_tenant(staging, "zenith")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_zenith_second_repair_noop_preserves_files(self) -> None:
        """Second zenith repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("zenith_noop")
        _repair_tenant(staging, "zenith", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "zenith", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest

class TestHeldOutLumenTenant:
    def test_lumen_overlay_applied(self) -> None:
        """Held-out lumen tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("lumen_overlay")
        manifest = _repair_tenant(staging, "lumen", "fix_lumen.json")
        assert manifest["tenant"] == "lumen"
        assert "ChallengeResponseAuthentication no" in _sshd_conf(staging)

    def test_lumen_ignores_seeded_registry_cache(self) -> None:
        """Lumen repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("lumen_cache")
        _repair_tenant(staging, "lumen")
        conf = _sshd_conf(staging)
        assert "ChallengeResponseAuthentication no" in conf
        assert "ChallengeResponseAuthentication yes" not in conf

    def test_lumen_tenant_audit_clean_after_repair(self) -> None:
        """Lumen repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("lumen_clean")
        _repair_tenant(staging, "lumen")
        report = _audit_tenant(staging, "lumen", "audit_lumen.json")
        assert report["tenant"] == "lumen"
        assert report["clean"] is True

    def test_lumen_manifest_digest_matches_sorted_changes(self) -> None:
        """Lumen manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("lumen_manifest")
        manifest = _repair_tenant(staging, "lumen")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_lumen_second_repair_noop_preserves_files(self) -> None:
        """Second lumen repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("lumen_noop")
        _repair_tenant(staging, "lumen", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "lumen", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutCobaltTenant:
    def test_cobalt_overlay_applied(self) -> None:
        """Held-out cobalt tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("cobalt_overlay")
        manifest = _repair_tenant(staging, "cobalt", "fix_cobalt.json")
        assert manifest["tenant"] == "cobalt"
        assert "GSSAPIAuthentication no" in _sshd_conf(staging)

    def test_cobalt_ignores_seeded_registry_cache(self) -> None:
        """Cobalt repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("cobalt_cache")
        _repair_tenant(staging, "cobalt")
        conf = _sshd_conf(staging)
        assert "GSSAPIAuthentication no" in conf
        assert "GSSAPIAuthentication yes" not in conf

    def test_cobalt_tenant_audit_clean_after_repair(self) -> None:
        """Cobalt repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("cobalt_clean")
        _repair_tenant(staging, "cobalt")
        report = _audit_tenant(staging, "cobalt", "audit_cobalt.json")
        assert report["tenant"] == "cobalt"
        assert report["clean"] is True

    def test_cobalt_manifest_digest_matches_sorted_changes(self) -> None:
        """Cobalt manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("cobalt_manifest")
        manifest = _repair_tenant(staging, "cobalt")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_cobalt_second_repair_noop_preserves_files(self) -> None:
        """Second cobalt repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("cobalt_noop")
        _repair_tenant(staging, "cobalt", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "cobalt", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutVectorTenant:
    def test_vector_overlay_applied(self) -> None:
        """Held-out vector tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("vector_overlay")
        manifest = _repair_tenant(staging, "vector", "fix_vector.json")
        assert manifest["tenant"] == "vector"
        assert "HostKeyAlgorithms ssh-ed25519" in _sshd_conf(staging)

    def test_vector_ignores_seeded_registry_cache(self) -> None:
        """Vector repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("vector_cache")
        _repair_tenant(staging, "vector")
        conf = _sshd_conf(staging)
        assert "HostKeyAlgorithms ssh-ed25519" in conf
        assert "HostKeyAlgorithms ssh-rsa" not in conf

    def test_vector_tenant_audit_clean_after_repair(self) -> None:
        """Vector repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("vector_clean")
        _repair_tenant(staging, "vector")
        report = _audit_tenant(staging, "vector", "audit_vector.json")
        assert report["tenant"] == "vector"
        assert report["clean"] is True

    def test_vector_manifest_digest_matches_sorted_changes(self) -> None:
        """Vector manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("vector_manifest")
        manifest = _repair_tenant(staging, "vector")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_vector_second_repair_noop_preserves_files(self) -> None:
        """Second vector repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("vector_noop")
        _repair_tenant(staging, "vector", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "vector", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestDeepHardeningRoundJ:
    def test_zenith_and_aurora_repairs_remain_distinct(self) -> None:
        """Zenith and aurora sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundj_zenith")
        b = _fresh_staging("roundj_aurora")
        _repair_tenant(a, "zenith")
        _repair_tenant(b, "aurora")
        assert "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u" in _sshd_conf(a)
        assert "AddressFamily inet" in _sshd_conf(b)
        assert "AddressFamily inet" not in _sshd_conf(a)

    def test_lumen_and_helix_repairs_remain_distinct(self) -> None:
        """Lumen and helix sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundj_lumen")
        b = _fresh_staging("roundj_helix")
        _repair_tenant(a, "lumen")
        _repair_tenant(b, "helix")
        assert "ChallengeResponseAuthentication no" in _sshd_conf(a)
        assert "HostbasedAuthentication no" in _sshd_conf(b)
        assert "HostbasedAuthentication no" not in _sshd_conf(a)

    def test_cobalt_and_vertex_repairs_remain_distinct(self) -> None:
        """Cobalt and vertex sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundj_cobalt")
        b = _fresh_staging("roundj_vertex")
        _repair_tenant(a, "cobalt")
        _repair_tenant(b, "vertex")
        assert "GSSAPIAuthentication no" in _sshd_conf(a)
        assert "PermitEmptyPasswords no" in _sshd_conf(b)
        assert "PermitEmptyPasswords no" not in _sshd_conf(a)

    def test_vector_and_continuum_repairs_remain_distinct(self) -> None:
        """Vector and continuum sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundj_vector")
        b = _fresh_staging("roundj_continuum")
        _repair_tenant(a, "vector")
        _repair_tenant(b, "continuum")
        assert "HostKeyAlgorithms ssh-ed25519" in _sshd_conf(a)
        assert "StreamLocalBindMask 077" in _sshd_conf(b)
        assert "StreamLocalBindMask 077" not in _sshd_conf(a)


class TestDeskTrapBehavioralRound5:
    def test_zenith_cache_desk_is_decoy(self) -> None:
        """Zenith cache desk exists but repair follows live overlay not cache."""
        desk = Path("/app/docs/zenith_cache_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_zenith")
        _repair_tenant(staging, "zenith")
        assert "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u" in _sshd_conf(staging)

    def test_lumen_alias_desk_is_decoy(self) -> None:
        """Lumen alias desk exists but repair uses lumen tenant overlay not staging."""
        desk = Path("/app/docs/lumen_alias_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_lumen")
        _repair_tenant(staging, "lumen")
        assert "ChallengeResponseAuthentication no" in _sshd_conf(staging)

    def test_cobalt_global_first_desk_is_decoy(self) -> None:
        """Cobalt global-first desk exists but tenant overlay leaves win."""
        desk = Path("/app/docs/cobalt_global_first_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_cobalt")
        _repair_tenant(staging, "cobalt")
        assert "GSSAPIAuthentication no" in _sshd_conf(staging)

    def test_vector_snapshot_desk_is_decoy(self) -> None:
        """Vector snapshot desk exists but repair uses live registry not archive snapshot."""
        desk = Path("/app/docs/vector_snapshot_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_vector")
        _repair_tenant(staging, "vector")
        assert "HostKeyAlgorithms ssh-ed25519" in _sshd_conf(staging)


class TestCrossTenantIsolationRound5:
    @pytest.mark.parametrize(
        "left,right,left_marker,right_marker",
        [
            ("zenith", "nexus", "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u", "ClientAliveInterval 120"),
            ("lumen", "rift", "ChallengeResponseAuthentication no", "MaxSessions 4"),
            ("cobalt", "prism", "GSSAPIAuthentication no", "LogLevel VERBOSE"),
            ("vector", "quasar", "HostKeyAlgorithms ssh-ed25519", "PermitTTY no"),
            ("zenith", "atlas", "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u", "Compression yes"),
            ("lumen", "comet", "ChallengeResponseAuthentication no", "Banner /etc/issue.net"),
            ("cobalt", "orbit", "GSSAPIAuthentication no", "StrictModes yes"),
            ("vector", "pulse", "HostKeyAlgorithms ssh-ed25519", "KexAlgorithms curve25519-sha256"),
            ("zenith", "eclipse", "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u", "PrintMotd no"),
            ("lumen", "nebula", "ChallengeResponseAuthentication no", "TCPKeepAlive yes"),
            ("cobalt", "solstice", "GSSAPIAuthentication no", "PermitUserEnvironment no"),
            ("vector", "pulsar", "HostKeyAlgorithms ssh-ed25519", "GatewayPorts no"),
        ],
    )
    def test_round3_and_legacy_tenant_sshd_directives_differ(
        self, left: str, right: str, left_marker: str, right_marker: str
    ) -> None:
        """Round-three held-out tenants remain isolated from legacy tenant sshd exports."""
        a = _fresh_staging(f"iso5_{left}")
        b = _fresh_staging(f"iso5_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert left_marker in _sshd_conf(a)
        assert right_marker in _sshd_conf(b)
        assert right_marker not in _sshd_conf(a)


class TestRepairSequenceDepthRound3:
    @pytest.mark.parametrize("tenant", ROUND3_HELD_OUT_TENANTS)
    def test_third_repair_still_noop(self, tenant: str) -> None:
        """Third repair on round-three tenant staging remains noop."""
        staging = _fresh_staging(f"seq3_{tenant}_third")
        for index in range(1, 3):
            _repair_tenant(staging, tenant, f"fix{index}.json")
        manifest = _repair_tenant(staging, tenant, "fix3.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", ROUND3_HELD_OUT_TENANTS)
    def test_first_and_second_manifest_hashes_differ_then_stable(self, tenant: str) -> None:
        """First repair manifest hash differs from second noop digest for round-three tenants."""
        staging = _fresh_staging(f"seq3_{tenant}_hash")
        first = _repair_tenant(staging, tenant, "fix1.json")
        second = _repair_tenant(staging, tenant, "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])


ROUND4_HELD_OUT_TENANTS = ["horizon", "flux", "apex", "relay"]


class TestTenantPostRepairModeSweepRoundM:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_alice_ssh_directory_mode(self, tenant: str) -> None:
        """Post-repair alice .ssh directory mode matches registry 0700 for every tenant."""
        staging = _fresh_staging(f"rm_alice_dir_{tenant}")
        _repair_tenant(staging, tenant)
        mode = oct(_path_mode_bits(staging / "extracted/homes/alice/.ssh"))[2:]
        assert mode in {"700", "0700"}, tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_bob_ssh_directory_mode(self, tenant: str) -> None:
        """Post-repair bob .ssh directory mode matches registry 0700 for every tenant."""
        staging = _fresh_staging(f"rm_bob_dir_{tenant}")
        _repair_tenant(staging, tenant)
        mode = oct(_path_mode_bits(staging / "extracted/homes/bob/.ssh"))[2:]
        assert mode in {"700", "0700"}, tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_alice_authorized_keys_mode(self, tenant: str) -> None:
        """Post-repair alice authorized_keys mode matches registry 0600 for every tenant."""
        staging = _fresh_staging(f"rm_alice_key_{tenant}")
        _repair_tenant(staging, tenant)
        mode = oct(
            _path_mode_bits(
                staging / "extracted/homes/alice/.ssh/authorized_keys"
            )
        )[2:]
        assert mode in {"600", "0600"}, tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_bob_authorized_keys_mode(self, tenant: str) -> None:
        """Post-repair bob authorized_keys mode matches registry 0600 for every tenant."""
        staging = _fresh_staging(f"rm_bob_key_{tenant}")
        _repair_tenant(staging, tenant)
        mode = oct(
            _path_mode_bits(
                staging / "extracted/homes/bob/.ssh/authorized_keys"
            )
        )[2:]
        assert mode in {"600", "0600"}, tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_mode_paths_absent_from_manifest(self, tenant: str) -> None:
        """Mode-only ssh paths stay out of manifest while on-disk modes are repaired."""
        staging = _fresh_staging(f"rm_manifest_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        _assert_manifest_excludes_mode_only_directories(manifest)
        assert _path_mode_bits(staging / "extracted/homes/alice/.ssh") == 0o700
        assert (
            _path_mode_bits(
                staging / "extracted/homes/alice/.ssh/authorized_keys"
            )
            == 0o600
        )


class TestHeldOutHorizonTenant:
    def test_horizon_overlay_applied(self) -> None:
        """Held-out horizon tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("horizon_overlay")
        manifest = _repair_tenant(staging, "horizon", "fix_horizon.json")
        assert manifest["tenant"] == "horizon"
        assert "X11UseLocalhost no" in _sshd_conf(staging)

    def test_horizon_ignores_seeded_registry_cache(self) -> None:
        """Horizon repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("horizon_cache")
        _repair_tenant(staging, "horizon")
        conf = _sshd_conf(staging)
        assert "X11UseLocalhost no" in conf
        assert "X11UseLocalhost yes" not in conf

    def test_horizon_tenant_audit_clean_after_repair(self) -> None:
        """Horizon repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("horizon_clean")
        _repair_tenant(staging, "horizon")
        report = _audit_tenant(staging, "horizon", "audit_horizon.json")
        assert report["tenant"] == "horizon"
        assert report["clean"] is True

    def test_horizon_manifest_digest_matches_sorted_changes(self) -> None:
        """Horizon manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("horizon_manifest")
        manifest = _repair_tenant(staging, "horizon")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_horizon_second_repair_noop_preserves_files(self) -> None:
        """Second horizon repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("horizon_noop")
        _repair_tenant(staging, "horizon", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "horizon", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutFluxTenant:
    def test_flux_overlay_applied(self) -> None:
        """Held-out flux tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("flux_overlay")
        manifest = _repair_tenant(staging, "flux", "fix_flux.json")
        assert manifest["tenant"] == "flux"
        assert "ClientAliveCountMax 3" in _sshd_conf(staging)

    def test_flux_ignores_seeded_registry_cache(self) -> None:
        """Flux repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("flux_cache")
        _repair_tenant(staging, "flux")
        conf = _sshd_conf(staging)
        assert "ClientAliveCountMax 3" in conf
        assert "ClientAliveCountMax 10" not in conf

    def test_flux_tenant_audit_clean_after_repair(self) -> None:
        """Flux repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("flux_clean")
        _repair_tenant(staging, "flux")
        report = _audit_tenant(staging, "flux", "audit_flux.json")
        assert report["tenant"] == "flux"
        assert report["clean"] is True

    def test_flux_manifest_digest_matches_sorted_changes(self) -> None:
        """Flux manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("flux_manifest")
        manifest = _repair_tenant(staging, "flux")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_flux_second_repair_noop_preserves_files(self) -> None:
        """Second flux repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("flux_noop")
        _repair_tenant(staging, "flux", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "flux", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutApexTenant:
    def test_apex_overlay_applied(self) -> None:
        """Held-out apex tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("apex_overlay")
        manifest = _repair_tenant(staging, "apex", "fix_apex.json")
        assert manifest["tenant"] == "apex"
        assert "Ciphers chacha20-poly1305@openssh.com" in _sshd_conf(staging)

    def test_apex_ignores_seeded_registry_cache(self) -> None:
        """Apex repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("apex_cache")
        _repair_tenant(staging, "apex")
        conf = _sshd_conf(staging)
        assert "Ciphers chacha20-poly1305@openssh.com" in conf
        assert "Ciphers aes256-ctr" not in conf

    def test_apex_tenant_audit_clean_after_repair(self) -> None:
        """Apex repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("apex_clean")
        _repair_tenant(staging, "apex")
        report = _audit_tenant(staging, "apex", "audit_apex.json")
        assert report["tenant"] == "apex"
        assert report["clean"] is True

    def test_apex_manifest_digest_matches_sorted_changes(self) -> None:
        """Apex manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("apex_manifest")
        manifest = _repair_tenant(staging, "apex")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_apex_second_repair_noop_preserves_files(self) -> None:
        """Second apex repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("apex_noop")
        _repair_tenant(staging, "apex", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "apex", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutRelayTenant:
    def test_relay_overlay_applied(self) -> None:
        """Held-out relay tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("relay_overlay")
        manifest = _repair_tenant(staging, "relay", "fix_relay.json")
        assert manifest["tenant"] == "relay"
        assert "KbdInteractiveAuthentication no" in _sshd_conf(staging)

    def test_relay_ignores_seeded_registry_cache(self) -> None:
        """Relay repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("relay_cache")
        _repair_tenant(staging, "relay")
        conf = _sshd_conf(staging)
        assert "KbdInteractiveAuthentication no" in conf
        assert "KbdInteractiveAuthentication yes" not in conf

    def test_relay_tenant_audit_clean_after_repair(self) -> None:
        """Relay repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("relay_clean")
        _repair_tenant(staging, "relay")
        report = _audit_tenant(staging, "relay", "audit_relay.json")
        assert report["tenant"] == "relay"
        assert report["clean"] is True

    def test_relay_manifest_digest_matches_sorted_changes(self) -> None:
        """Relay manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("relay_manifest")
        manifest = _repair_tenant(staging, "relay")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_relay_second_repair_noop_preserves_files(self) -> None:
        """Second relay repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("relay_noop")
        _repair_tenant(staging, "relay", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "relay", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestDeepHardeningRoundK:
    def test_horizon_and_zenith_repairs_remain_distinct(self) -> None:
        """Horizon and zenith sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundk_horizon")
        b = _fresh_staging("roundk_zenith")
        _repair_tenant(a, "horizon")
        _repair_tenant(b, "zenith")
        assert "X11UseLocalhost no" in _sshd_conf(a)
        assert "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u" in _sshd_conf(b)
        assert "X11UseLocalhost no" not in _sshd_conf(b)

    def test_flux_and_lumen_repairs_remain_distinct(self) -> None:
        """Flux and lumen sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundk_flux")
        b = _fresh_staging("roundk_lumen")
        _repair_tenant(a, "flux")
        _repair_tenant(b, "lumen")
        assert "ClientAliveCountMax 3" in _sshd_conf(a)
        assert "ChallengeResponseAuthentication no" in _sshd_conf(b)
        assert "ClientAliveCountMax 3" not in _sshd_conf(b)

    def test_apex_and_cobalt_repairs_remain_distinct(self) -> None:
        """Apex and cobalt sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundk_apex")
        b = _fresh_staging("roundk_cobalt")
        _repair_tenant(a, "apex")
        _repair_tenant(b, "cobalt")
        assert "Ciphers chacha20-poly1305@openssh.com" in _sshd_conf(a)
        assert "GSSAPIAuthentication no" in _sshd_conf(b)
        assert "Ciphers chacha20-poly1305@openssh.com" not in _sshd_conf(b)

    def test_relay_and_vector_repairs_remain_distinct(self) -> None:
        """Relay and vector sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundk_relay")
        b = _fresh_staging("roundk_vector")
        _repair_tenant(a, "relay")
        _repair_tenant(b, "vector")
        assert "KbdInteractiveAuthentication no" in _sshd_conf(a)
        assert "HostKeyAlgorithms ssh-ed25519" in _sshd_conf(b)
        assert "KbdInteractiveAuthentication no" not in _sshd_conf(b)

    def test_horizon_flux_apex_relay_audit_clean_independently(self) -> None:
        """Round-four held-out tenants each audit clean after scoped repair."""
        tenants = ["horizon", "flux", "apex", "relay"]
        stagings = [_fresh_staging(f"roundk_clean_{t}") for t in tenants]
        for staging, tenant in zip(stagings, tenants):
            _repair_tenant(staging, tenant)
        for staging, tenant in zip(stagings, tenants):
            assert _audit_tenant(staging, tenant)["clean"] is True


class TestDeskTrapBehavioralRound6:
    def test_horizon_cache_desk_is_decoy(self) -> None:
        """Horizon cache desk exists but repair follows live overlay not cache."""
        desk = Path("/app/docs/horizon_cache_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_horizon")
        _repair_tenant(staging, "horizon")
        assert "X11UseLocalhost no" in _sshd_conf(staging)

    def test_flux_alias_desk_is_decoy(self) -> None:
        """Flux alias desk exists but repair uses flux tenant overlay not staging."""
        desk = Path("/app/docs/flux_alias_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_flux")
        _repair_tenant(staging, "flux")
        assert "ClientAliveCountMax 3" in _sshd_conf(staging)

    def test_apex_global_first_desk_is_decoy(self) -> None:
        """Apex global-first desk exists but tenant overlay leaves win."""
        desk = Path("/app/docs/apex_global_first_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_apex")
        _repair_tenant(staging, "apex")
        assert "Ciphers chacha20-poly1305@openssh.com" in _sshd_conf(staging)

    def test_relay_snapshot_desk_is_decoy(self) -> None:
        """Relay snapshot desk exists but repair uses live registry not archive snapshot."""
        desk = Path("/app/docs/relay_snapshot_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_relay")
        _repair_tenant(staging, "relay")
        assert "KbdInteractiveAuthentication no" in _sshd_conf(staging)


class TestCrossTenantIsolationRound6:
    @pytest.mark.parametrize(
        "left,right,left_marker,right_marker",
        [
            ("horizon", "zenith", "X11UseLocalhost no", "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u"),
            ("flux", "lumen", "ClientAliveCountMax 3", "ChallengeResponseAuthentication no"),
            ("apex", "cobalt", "Ciphers chacha20-poly1305@openssh.com", "GSSAPIAuthentication no"),
            ("relay", "vector", "KbdInteractiveAuthentication no", "HostKeyAlgorithms ssh-ed25519"),
            ("horizon", "nexus", "X11UseLocalhost no", "ClientAliveInterval 120"),
            ("flux", "rift", "ClientAliveCountMax 3", "MaxSessions 4"),
            ("apex", "prism", "Ciphers chacha20-poly1305@openssh.com", "LogLevel VERBOSE"),
            ("relay", "quasar", "KbdInteractiveAuthentication no", "PermitTTY no"),
            ("horizon", "eclipse", "X11UseLocalhost no", "UsePAM yes"),
            ("flux", "nebula", "ClientAliveCountMax 3", "TCPKeepAlive yes"),
            ("apex", "solstice", "Ciphers chacha20-poly1305@openssh.com", "PermitUserEnvironment no"),
            ("relay", "pulsar", "KbdInteractiveAuthentication no", "GatewayPorts no"),
        ],
    )
    def test_round4_and_legacy_tenant_sshd_directives_differ(
        self, left: str, right: str, left_marker: str, right_marker: str
    ) -> None:
        """Round-four held-out tenants remain isolated from legacy tenant sshd exports."""
        a = _fresh_staging(f"iso6_{left}")
        b = _fresh_staging(f"iso6_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert left_marker in _sshd_conf(a)
        assert right_marker in _sshd_conf(b)
        assert right_marker not in _sshd_conf(a)


class TestRepairSequenceDepthRound4:
    @pytest.mark.parametrize("tenant", ROUND4_HELD_OUT_TENANTS)
    def test_third_repair_still_noop(self, tenant: str) -> None:
        """Third repair on round-four tenant staging remains noop."""
        staging = _fresh_staging(f"seq4_{tenant}_third")
        for index in range(1, 3):
            _repair_tenant(staging, tenant, f"fix{index}.json")
        manifest = _repair_tenant(staging, tenant, "fix3.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", ROUND4_HELD_OUT_TENANTS)
    def test_first_and_second_manifest_hashes_differ_then_stable(self, tenant: str) -> None:
        """First repair manifest hash differs from second noop digest for round-four tenants."""
        staging = _fresh_staging(f"seq4_{tenant}_hash")
        first = _repair_tenant(staging, tenant, "fix1.json")
        second = _repair_tenant(staging, tenant, "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])


class TestHandbookAmendmentRound4:
    def test_handbook_amendment_2025_15_horizon_flux(self) -> None:
        """Handbook Amendment 2025-15 names horizon and flux tenant tokens."""
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(encoding="utf-8")
        assert "Amendment 2025-15" in handbook
        assert "RULE:HORIZON_TENANT=horizon" in handbook
        assert "RULE:FLUX_TENANT=flux" in handbook

    def test_handbook_amendment_2025_16_apex_relay(self) -> None:
        """Handbook Amendment 2025-16 names apex and relay tenant tokens."""
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(encoding="utf-8")
        assert "Amendment 2025-16" in handbook
        assert "RULE:APEX_TENANT=apex" in handbook
        assert "RULE:RELAY_TENANT=relay" in handbook

    def test_handbook_file_modes_apply_off_manifest(self) -> None:
        """Amendment 2025-15 requires file_modes chmod even when omitted from manifest changes."""
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(encoding="utf-8")
        assert "homes/*/.ssh" in handbook or "homes/alice/.ssh" in handbook
        assert "Amendment 2025-10" in handbook


ROUND5_HELD_OUT_TENANTS = ["spire", "nova", "titan", "forge"]


class TestTenantPostRepairModeAndAuditRoundO:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_audit_clean_and_exact_modes(self, tenant: str) -> None:
        """Audit clean only counts when ssh directory and key modes are exact."""
        staging = _fresh_staging(f"ro_audit_mode_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is True, tenant
        assert report["violations"] == [], tenant
        assert _path_mode_bits(staging / "extracted/homes/alice/.ssh") == 0o700
        assert _path_mode_bits(staging / "extracted/homes/bob/.ssh") == 0o700
        assert (
            _path_mode_bits(
                staging / "extracted/homes/alice/.ssh/authorized_keys"
            )
            == 0o600
        )
        assert (
            _path_mode_bits(
                staging / "extracted/homes/bob/.ssh/authorized_keys"
            )
            == 0o600
        )

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_excludes_mode_paths_after_exact_mode_repair(
        self, tenant: str
    ) -> None:
        """Manifest omits mode-only paths while on-disk modes are exact."""
        staging = _fresh_staging(f"ro_manifest_mode_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        _assert_manifest_excludes_mode_only_directories(manifest)
        assert _path_mode_bits(staging / "extracted/homes/alice/.ssh") == 0o700


class TestTenantLiveKeyReRepairRoundO:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_second_repair_after_live_key_rotation(self, tenant: str) -> None:
        """Second repair after live key mutation restores audit-clean state."""
        staging = _fresh_staging(f"ro_keyrot_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        rotated = f"ssh-rsa ROTATED-{tenant.upper()} alice@corp"
        _redis_hset("bastion:ssh_keys", "alice", rotated)
        _repair_tenant(staging, tenant, "fix2.json")
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is True
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == rotated


class TestTenantCachePoisonIgnoredRoundO:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_runtime_cache_sshd_trap_ignored(self, tenant: str) -> None:
        """Runtime registry cache sshd trap must not override live overlay."""
        staging = _fresh_staging(f"ro_cache_{tenant}")
        _redis_hset(
            f"bastion:registry:cache:{tenant}",
            "sshd_settings",
            json.dumps(
                {
                    "ssh/sshd_config.d/bastion.conf": {
                        "AllowUsers": "eve",
                        "PasswordAuthentication": "yes",
                    }
                },
                separators=(",", ":"),
            ),
        )
        _repair_tenant(staging, tenant)
        conf = _sshd_conf(staging)
        assert "AllowUsers eve" not in conf
        assert "PasswordAuthentication yes" not in conf


class TestTenantFifthRepairNoopRoundP:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_fifth_repair_still_noop(self, tenant: str) -> None:
        """Fifth repair on tenant staging remains noop."""
        staging = _fresh_staging(f"rp_fifth_{tenant}")
        for index in range(1, 5):
            _repair_tenant(staging, tenant, f"fix{index}.json")
        manifest = _repair_tenant(staging, tenant, "fix5.json")
        assert manifest["noop"] is True
        assert manifest["changes"] == []


class TestTenantSequentialIsolationRoundP:
    @pytest.mark.parametrize("left,right", [
        ("prod", "spire"),
        ("staging", "nova"),
        ("nexus", "titan"),
        ("quasar", "forge"),
    ])
    def test_sequential_repairs_do_not_cross_contaminate(
        self, left: str, right: str
    ) -> None:
        """Sequential repairs on isolated trees keep tenant overlays separate."""
        a = _fresh_staging(f"rp_seq_{left}")
        b = _fresh_staging(f"rp_seq_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert _audit_tenant(a, left)["clean"] is True
        assert _audit_tenant(b, right)["clean"] is True
        assert _repair_tenant(a, left, "noop_a.json")["noop"] is True
        assert _repair_tenant(b, right, "noop_b.json")["noop"] is True


class TestHeldOutSpireTenant:
    def test_spire_overlay_applied(self) -> None:
        """Held-out spire tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("spire_overlay")
        manifest = _repair_tenant(staging, "spire", "fix_spire.json")
        assert manifest["tenant"] == "spire"
        assert "MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com" in _sshd_conf(staging)

    def test_spire_ignores_seeded_registry_cache(self) -> None:
        """Spire repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("spire_cache")
        _repair_tenant(staging, "spire")
        conf = _sshd_conf(staging)
        assert "MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com" in conf
        assert "MACs hmac-sha1" not in conf

    def test_spire_tenant_audit_clean_after_repair(self) -> None:
        """Spire repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("spire_clean")
        _repair_tenant(staging, "spire")
        report = _audit_tenant(staging, "spire", "audit_spire.json")
        assert report["tenant"] == "spire"
        assert report["clean"] is True

    def test_spire_manifest_digest_matches_sorted_changes(self) -> None:
        """Spire manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("spire_manifest")
        manifest = _repair_tenant(staging, "spire")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_spire_second_repair_noop_preserves_files(self) -> None:
        """Second spire repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("spire_noop")
        _repair_tenant(staging, "spire", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "spire", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutNovaTenant:
    def test_nova_overlay_applied(self) -> None:
        """Held-out nova tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("nova_overlay")
        manifest = _repair_tenant(staging, "nova", "fix_nova.json")
        assert manifest["tenant"] == "nova"
        assert "Subsystem sftp internal-sftp" in _sshd_conf(staging)

    def test_nova_ignores_seeded_registry_cache(self) -> None:
        """Nova repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("nova_cache")
        _repair_tenant(staging, "nova")
        conf = _sshd_conf(staging)
        assert "Subsystem sftp internal-sftp" in conf
        assert "Subsystem sftp /usr/lib/openssh/sftp-server" not in conf

    def test_nova_tenant_audit_clean_after_repair(self) -> None:
        """Nova repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("nova_clean")
        _repair_tenant(staging, "nova")
        report = _audit_tenant(staging, "nova", "audit_nova.json")
        assert report["tenant"] == "nova"
        assert report["clean"] is True

    def test_nova_manifest_digest_matches_sorted_changes(self) -> None:
        """Nova manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("nova_manifest")
        manifest = _repair_tenant(staging, "nova")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_nova_second_repair_noop_preserves_files(self) -> None:
        """Second nova repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("nova_noop")
        _repair_tenant(staging, "nova", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "nova", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutTitanTenant:
    def test_titan_overlay_applied(self) -> None:
        """Held-out titan tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("titan_overlay")
        manifest = _repair_tenant(staging, "titan", "fix_titan.json")
        assert manifest["tenant"] == "titan"
        assert "ForceCommand /usr/bin/ls" in _sshd_conf(staging)

    def test_titan_ignores_seeded_registry_cache(self) -> None:
        """Titan repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("titan_cache")
        _repair_tenant(staging, "titan")
        conf = _sshd_conf(staging)
        assert "ForceCommand /usr/bin/ls" in conf
        assert "ForceCommand /bin/false" not in conf

    def test_titan_tenant_audit_clean_after_repair(self) -> None:
        """Titan repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("titan_clean")
        _repair_tenant(staging, "titan")
        report = _audit_tenant(staging, "titan", "audit_titan.json")
        assert report["tenant"] == "titan"
        assert report["clean"] is True

    def test_titan_manifest_digest_matches_sorted_changes(self) -> None:
        """Titan manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("titan_manifest")
        manifest = _repair_tenant(staging, "titan")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_titan_second_repair_noop_preserves_files(self) -> None:
        """Second titan repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("titan_noop")
        _repair_tenant(staging, "titan", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "titan", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestHeldOutForgeTenant:
    def test_forge_overlay_applied(self) -> None:
        """Held-out forge tenant applies ratified sshd overlay directives."""
        staging = _fresh_staging("forge_overlay")
        manifest = _repair_tenant(staging, "forge", "fix_forge.json")
        assert manifest["tenant"] == "forge"
        assert "PermitOpen localhost:8080" in _sshd_conf(staging)

    def test_forge_ignores_seeded_registry_cache(self) -> None:
        """Forge repair uses live overlay not stale registry cache."""
        staging = _fresh_staging("forge_cache")
        _repair_tenant(staging, "forge")
        conf = _sshd_conf(staging)
        assert "PermitOpen localhost:8080" in conf
        assert "PermitOpen any" not in conf

    def test_forge_tenant_audit_clean_after_repair(self) -> None:
        """Forge repair then audit is clean with matching staging_root."""
        staging = _fresh_staging("forge_clean")
        _repair_tenant(staging, "forge")
        report = _audit_tenant(staging, "forge", "audit_forge.json")
        assert report["tenant"] == "forge"
        assert report["clean"] is True

    def test_forge_manifest_digest_matches_sorted_changes(self) -> None:
        """Forge manifest_sha256 hashes compact sorted changes array only."""
        staging = _fresh_staging("forge_manifest")
        manifest = _repair_tenant(staging, "forge")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_forge_second_repair_noop_preserves_files(self) -> None:
        """Second forge repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("forge_noop")
        _repair_tenant(staging, "forge", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "forge", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestDeepHardeningRoundL:
    def test_spire_and_horizon_repairs_remain_distinct(self) -> None:
        """Spire and horizon sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundl_spire")
        b = _fresh_staging("roundl_horizon")
        _repair_tenant(a, "spire")
        _repair_tenant(b, "horizon")
        assert "MACs hmac-sha2-512-etm@openssh.com" in _sshd_conf(a)
        assert "X11UseLocalhost no" in _sshd_conf(b)
        assert "X11UseLocalhost no" not in _sshd_conf(a)

    def test_nova_and_flux_repairs_remain_distinct(self) -> None:
        """Nova and flux sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundl_nova")
        b = _fresh_staging("roundl_flux")
        _repair_tenant(a, "nova")
        _repair_tenant(b, "flux")
        assert "Subsystem sftp internal-sftp" in _sshd_conf(a)
        assert "ClientAliveCountMax 3" in _sshd_conf(b)
        assert "ClientAliveCountMax 3" not in _sshd_conf(a)

    def test_titan_and_apex_repairs_remain_distinct(self) -> None:
        """Titan and apex sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundl_titan")
        b = _fresh_staging("roundl_apex")
        _repair_tenant(a, "titan")
        _repair_tenant(b, "apex")
        assert "ForceCommand /usr/bin/ls" in _sshd_conf(a)
        assert "Ciphers chacha20-poly1305@openssh.com" in _sshd_conf(b)
        assert "Ciphers chacha20-poly1305@openssh.com" not in _sshd_conf(a)

    def test_forge_and_relay_repairs_remain_distinct(self) -> None:
        """Forge and relay sibling repairs do not cross-contaminate sshd directives."""
        a = _fresh_staging("roundl_forge")
        b = _fresh_staging("roundl_relay")
        _repair_tenant(a, "forge")
        _repair_tenant(b, "relay")
        assert "PermitOpen localhost:8080" in _sshd_conf(a)
        assert "KbdInteractiveAuthentication no" in _sshd_conf(b)
        assert "KbdInteractiveAuthentication no" not in _sshd_conf(a)


class TestDeskTrapBehavioralRound7:
    def test_spire_cache_desk_is_decoy(self) -> None:
        """Spire cache desk exists but repair follows live overlay not cache."""
        desk = Path("/app/docs/spire_cache_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_spire")
        _repair_tenant(staging, "spire")
        assert "MACs hmac-sha2-512-etm@openssh.com" in _sshd_conf(staging)

    def test_nova_alias_desk_is_decoy(self) -> None:
        """Nova alias desk exists but repair uses nova tenant overlay not staging."""
        desk = Path("/app/docs/nova_alias_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_nova")
        _repair_tenant(staging, "nova")
        assert "Subsystem sftp internal-sftp" in _sshd_conf(staging)

    def test_titan_global_first_desk_is_decoy(self) -> None:
        """Titan global-first desk exists but tenant overlay leaves win."""
        desk = Path("/app/docs/titan_global_first_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_titan")
        _repair_tenant(staging, "titan")
        assert "ForceCommand /usr/bin/ls" in _sshd_conf(staging)

    def test_forge_snapshot_desk_is_decoy(self) -> None:
        """Forge snapshot desk exists but repair uses live registry not archive snapshot."""
        desk = Path("/app/docs/forge_snapshot_desk.md")
        assert desk.is_file()
        staging = _fresh_staging("desk_forge")
        _repair_tenant(staging, "forge")
        assert "PermitOpen localhost:8080" in _sshd_conf(staging)


class TestCrossTenantIsolationRound7:
    @pytest.mark.parametrize(
        "left,right,left_marker,right_marker",
        [
            ("spire", "horizon", "MACs hmac-sha2-512-etm@openssh.com", "X11UseLocalhost no"),
            ("nova", "flux", "Subsystem sftp internal-sftp", "ClientAliveCountMax 3"),
            ("titan", "apex", "ForceCommand /usr/bin/ls", "Ciphers chacha20-poly1305@openssh.com"),
            ("forge", "relay", "PermitOpen localhost:8080", "KbdInteractiveAuthentication no"),
            ("spire", "nexus", "MACs hmac-sha2-512-etm@openssh.com", "ClientAliveInterval 120"),
            ("nova", "rift", "Subsystem sftp internal-sftp", "MaxSessions 4"),
            ("titan", "prism", "ForceCommand /usr/bin/ls", "LogLevel VERBOSE"),
            ("forge", "quasar", "PermitOpen localhost:8080", "PermitTTY no"),
            ("spire", "zenith", "MACs hmac-sha2-512-etm@openssh.com", "AuthorizedKeysFile /etc/ssh/authorized_keys.d/%u"),
            ("nova", "lumen", "Subsystem sftp internal-sftp", "ChallengeResponseAuthentication no"),
            ("titan", "cobalt", "ForceCommand /usr/bin/ls", "GSSAPIAuthentication no"),
            ("forge", "vector", "PermitOpen localhost:8080", "HostKeyAlgorithms ssh-ed25519"),
        ],
    )
    def test_round5_and_legacy_tenant_sshd_directives_differ(
        self, left: str, right: str, left_marker: str, right_marker: str
    ) -> None:
        """Round-five held-out tenants remain isolated from legacy tenant sshd exports."""
        a = _fresh_staging(f"iso7_{left}")
        b = _fresh_staging(f"iso7_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert left_marker in _sshd_conf(a)
        assert right_marker in _sshd_conf(b)
        assert right_marker not in _sshd_conf(a)


class TestRepairSequenceDepthRound5:
    @pytest.mark.parametrize("tenant", ROUND5_HELD_OUT_TENANTS)
    def test_third_repair_still_noop(self, tenant: str) -> None:
        """Third repair on round-five tenant staging remains noop."""
        staging = _fresh_staging(f"seq5_{tenant}_third")
        for index in range(1, 3):
            _repair_tenant(staging, tenant, f"fix{index}.json")
        manifest = _repair_tenant(staging, tenant, "fix3.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", ROUND5_HELD_OUT_TENANTS)
    def test_first_and_second_manifest_hashes_differ_then_stable(self, tenant: str) -> None:
        """First repair manifest hash differs from second noop digest for round-five tenants."""
        staging = _fresh_staging(f"seq5_{tenant}_hash")
        first = _repair_tenant(staging, tenant, "fix1.json")
        second = _repair_tenant(staging, tenant, "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])


class TestHandbookAmendmentRound5:
    def test_handbook_amendment_2025_17_spire_nova(self) -> None:
        """Handbook Amendment 2025-17 names spire and nova tenant tokens."""
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(encoding="utf-8")
        assert "Amendment 2025-17" in handbook
        assert "RULE:SPIRE_TENANT=spire" in handbook
        assert "RULE:NOVA_TENANT=nova" in handbook

    def test_handbook_amendment_2025_18_titan_forge(self) -> None:
        """Handbook Amendment 2025-18 names titan and forge tenant tokens."""
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(encoding="utf-8")
        assert "Amendment 2025-18" in handbook
        assert "RULE:TITAN_TENANT=titan" in handbook
        assert "RULE:FORGE_TENANT=forge" in handbook

ROUND6_HELD_OUT_TENANTS = ["ember", "onyx", "sentinel", "cipher"]


class TestRepairAuditSequenceRoundQ:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_repair_then_audit_preserves_repairs(self, tenant: str) -> None:
        """Repair followed by audit on same staging tree must stay clean."""
        staging = _fresh_staging(f"rq_seq_{tenant}")
        _repair_tenant(staging, tenant)
        conf_before = _sshd_conf(staging)
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is True, tenant
        assert report["violations"] == [], tenant
        assert _sshd_conf(staging) == conf_before, tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_double_audit_after_repair_stays_clean(self, tenant: str) -> None:
        """Two audits after repair must both report clean without drift."""
        staging = _fresh_staging(f"rq_dblaudit_{tenant}")
        _repair_tenant(staging, tenant)
        first = _audit_tenant(staging, tenant, "audit1.json")
        second = _audit_tenant(staging, tenant, "audit2.json")
        assert first["clean"] is True
        assert second["clean"] is True
        assert first["violations"] == []
        assert second["violations"] == []

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_repair_audit_repair_noop_chain(self, tenant: str) -> None:
        """Repair, audit, second repair must noop when tree already clean."""
        staging = _fresh_staging(f"rq_chain_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        assert _audit_tenant(staging, tenant)["clean"] is True
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["noop"] is True
        assert manifest["changes"] == []


class TestTenantViolationKindSweepRoundQ:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_has_ssh_key_mismatch(self, tenant: str) -> None:
        """Fresh extract must report ssh_key_mismatch before repair."""
        staging = _fresh_staging(f"rq_pre_ssh_{tenant}")
        _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                tenant,
                "--report",
                str(staging / "pre.json"),
            ],
            check=False,
        )
        report = json.loads((staging / "pre.json").read_text(encoding="utf-8"))
        kinds = {v["kind"] for v in report["violations"]}
        assert "ssh_key_mismatch" in kinds

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_violation_kinds_empty(self, tenant: str) -> None:
        """Post-repair audit must report zero violations of every kind."""
        staging = _fresh_staging(f"rq_post_kinds_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["violations"] == []


class TestTenantSshdMarkerSweepRoundR:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_allowusers_alice(self, tenant: str) -> None:
        """Every tenant overlay keeps AllowUsers alice after repair."""
        staging = _fresh_staging(f"rr_allow_{tenant}")
        _repair_tenant(staging, tenant)
        assert "AllowUsers alice" in _sshd_conf(staging)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_password_auth_no(self, tenant: str) -> None:
        """Every tenant overlay keeps PasswordAuthentication no after repair."""
        staging = _fresh_staging(f"rr_pwd_{tenant}")
        _repair_tenant(staging, tenant)
        assert "PasswordAuthentication no" in _sshd_conf(staging)

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_not_clean(self, tenant: str) -> None:
        """Pre-repair audit must not be clean on pristine bundle."""
        staging = _fresh_staging(f"rr_preclean_{tenant}")
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is False
        assert len(report["violations"]) > 0


class TestTenantManifestDepthSweepRoundR:
    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_first_repair_changes_non_empty(self, tenant: str) -> None:
        """First repair on drifted bundle must emit non-empty changes."""
        staging = _fresh_staging(f"rr_changes_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["noop"] is False
        assert len(manifest["changes"]) > 0

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_changes_paths_relative(self, tenant: str) -> None:
        """Manifest change paths must be staging-relative not absolute."""
        staging = _fresh_staging(f"rr_relpath_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            assert not change["path"].startswith("/")

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_tenant_field(self, tenant: str) -> None:
        """Manifest tenant field must match CLI --tenant flag."""
        staging = _fresh_staging(f"rr_tenant_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        assert manifest["tenant"] == tenant


class TestTenantSequentialIsolationRoundQ:
    @pytest.mark.parametrize("left,right", [
        ("ember", "onyx"),
        ("sentinel", "cipher"),
        ("spire", "ember"),
        ("nova", "sentinel"),
        ("titan", "cipher"),
        ("forge", "onyx"),
    ])
    def test_round6_repairs_remain_isolated(self, left: str, right: str) -> None:
        """Round-6 held-out tenants repair independently on isolated trees."""
        a = _fresh_staging(f"rq_iso_{left}")
        b = _fresh_staging(f"rq_iso_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert _audit_tenant(a, left)["clean"] is True
        assert _audit_tenant(b, right)["clean"] is True
        assert _sshd_conf(a) != _sshd_conf(b)



class TestHeldOutEmberTenant:
    def test_ember_overlay_applied(self) -> None:
        """Held-out ember tenant sshd overlay must be applied on repair."""
        staging = _fresh_staging("ember_overlay")
        _repair_tenant(staging, "ember")
        conf = _sshd_conf(staging)
        assert "Compression delayed" in conf
        assert "Compression yes" not in conf

    def test_ember_ignores_seeded_registry_cache(self) -> None:
        """ember repair must ignore seeded registry cache sshd trap."""
        staging = _fresh_staging("ember_cache")
        _repair_tenant(staging, "ember")
        conf = _sshd_conf(staging)
        assert "Compression yes" not in conf

    def test_ember_tenant_audit_clean_after_repair(self) -> None:
        """ember audit must be clean after repair without re-wiping staging."""
        staging = _fresh_staging("ember_audit")
        _repair_tenant(staging, "ember")
        report = _audit_tenant(staging, "ember")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_ember_manifest_digest_matches_sorted_changes(self) -> None:
        """ember manifest_sha256 must match sorted changes array digest."""
        staging = _fresh_staging("ember_digest")
        manifest = _repair_tenant(staging, "ember")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_ember_second_repair_noop_preserves_files(self) -> None:
        """Second ember repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("ember_noop")
        _repair_tenant(staging, "ember", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "ember", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutOnyxTenant:
    def test_onyx_overlay_applied(self) -> None:
        """Held-out onyx tenant sshd overlay must be applied on repair."""
        staging = _fresh_staging("onyx_overlay")
        _repair_tenant(staging, "onyx")
        conf = _sshd_conf(staging)
        assert "PrintMotd no" in conf
        assert "PrintMotd yes" not in conf

    def test_onyx_ignores_seeded_registry_cache(self) -> None:
        """onyx repair must ignore seeded registry cache sshd trap."""
        staging = _fresh_staging("onyx_cache")
        _repair_tenant(staging, "onyx")
        conf = _sshd_conf(staging)
        assert "PrintMotd yes" not in conf

    def test_onyx_tenant_audit_clean_after_repair(self) -> None:
        """onyx audit must be clean after repair without re-wiping staging."""
        staging = _fresh_staging("onyx_audit")
        _repair_tenant(staging, "onyx")
        report = _audit_tenant(staging, "onyx")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_onyx_manifest_digest_matches_sorted_changes(self) -> None:
        """onyx manifest_sha256 must match sorted changes array digest."""
        staging = _fresh_staging("onyx_digest")
        manifest = _repair_tenant(staging, "onyx")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_onyx_second_repair_noop_preserves_files(self) -> None:
        """Second onyx repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("onyx_noop")
        _repair_tenant(staging, "onyx", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "onyx", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutSentinelTenant:
    def test_sentinel_overlay_applied(self) -> None:
        """Held-out sentinel tenant sshd overlay must be applied on repair."""
        staging = _fresh_staging("sentinel_overlay")
        _repair_tenant(staging, "sentinel")
        conf = _sshd_conf(staging)
        assert "StrictModes yes" in conf
        assert "StrictModes no" not in conf

    def test_sentinel_ignores_seeded_registry_cache(self) -> None:
        """sentinel repair must ignore seeded registry cache sshd trap."""
        staging = _fresh_staging("sentinel_cache")
        _repair_tenant(staging, "sentinel")
        conf = _sshd_conf(staging)
        assert "StrictModes no" not in conf

    def test_sentinel_tenant_audit_clean_after_repair(self) -> None:
        """sentinel audit must be clean after repair without re-wiping staging."""
        staging = _fresh_staging("sentinel_audit")
        _repair_tenant(staging, "sentinel")
        report = _audit_tenant(staging, "sentinel")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_sentinel_manifest_digest_matches_sorted_changes(self) -> None:
        """sentinel manifest_sha256 must match sorted changes array digest."""
        staging = _fresh_staging("sentinel_digest")
        manifest = _repair_tenant(staging, "sentinel")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_sentinel_second_repair_noop_preserves_files(self) -> None:
        """Second sentinel repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("sentinel_noop")
        _repair_tenant(staging, "sentinel", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "sentinel", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutCipherTenant:
    def test_cipher_overlay_applied(self) -> None:
        """Held-out cipher tenant sshd overlay must be applied on repair."""
        staging = _fresh_staging("cipher_overlay")
        _repair_tenant(staging, "cipher")
        conf = _sshd_conf(staging)
        assert "Ciphers aes256-gcm@openssh.com" in conf
        assert "Ciphers aes128-cbc" not in conf

    def test_cipher_ignores_seeded_registry_cache(self) -> None:
        """cipher repair must ignore seeded registry cache sshd trap."""
        staging = _fresh_staging("cipher_cache")
        _repair_tenant(staging, "cipher")
        conf = _sshd_conf(staging)
        assert "Ciphers aes128-cbc" not in conf

    def test_cipher_tenant_audit_clean_after_repair(self) -> None:
        """cipher audit must be clean after repair without re-wiping staging."""
        staging = _fresh_staging("cipher_audit")
        _repair_tenant(staging, "cipher")
        report = _audit_tenant(staging, "cipher")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_cipher_manifest_digest_matches_sorted_changes(self) -> None:
        """cipher manifest_sha256 must match sorted changes array digest."""
        staging = _fresh_staging("cipher_digest")
        manifest = _repair_tenant(staging, "cipher")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_cipher_second_repair_noop_preserves_files(self) -> None:
        """Second cipher repair is noop and preserves sshd conf digest."""
        staging = _fresh_staging("cipher_noop")
        _repair_tenant(staging, "cipher", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "cipher", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestDeepHardeningRoundM:
    def test_ember_and_spire_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundm_ember")
        b = _fresh_staging("roundm_spire")
        _repair_tenant(a, "ember")
        _repair_tenant(b, "spire")
        assert "Compression delayed" in _sshd_conf(a)
        assert "MACs hmac-sha2-512-etm@openssh.com" in _sshd_conf(b)
        assert "MACs hmac-sha2-512-etm@openssh.com" not in _sshd_conf(a)

    def test_onyx_and_nova_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundm_onyx")
        b = _fresh_staging("roundm_nova")
        _repair_tenant(a, "onyx")
        _repair_tenant(b, "nova")
        assert "PrintMotd no" in _sshd_conf(a)
        assert "Subsystem sftp internal-sftp" in _sshd_conf(b)

    def test_sentinel_and_horizon_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundm_sentinel")
        b = _fresh_staging("roundm_horizon")
        _repair_tenant(a, "sentinel")
        _repair_tenant(b, "horizon")
        assert "StrictModes yes" in _sshd_conf(a)
        assert "X11UseLocalhost no" in _sshd_conf(b)

    def test_cipher_and_apex_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundm_cipher")
        b = _fresh_staging("roundm_apex")
        _repair_tenant(a, "cipher")
        _repair_tenant(b, "apex")
        assert "Ciphers aes256-gcm@openssh.com" in _sshd_conf(a)
        assert "Ciphers chacha20-poly1305@openssh.com" in _sshd_conf(b)


class TestDeskTrapBehavioralRound8:
    def test_ember_cache_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/ember_cache_desk.md").read_text(encoding="utf-8")
        assert "Compression yes" in desk
        staging = _fresh_staging("desk_ember")
        _repair_tenant(staging, "ember")
        assert "Compression yes" not in _sshd_conf(staging)

    def test_onyx_alias_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/onyx_alias_desk.md").read_text(encoding="utf-8")
        assert "PrintMotd yes" in desk
        staging = _fresh_staging("desk_onyx")
        _repair_tenant(staging, "onyx")
        assert "PrintMotd yes" not in _sshd_conf(staging)

    def test_sentinel_global_first_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/sentinel_global_first_desk.md").read_text(encoding="utf-8")
        assert "StrictModes no" in desk
        staging = _fresh_staging("desk_sentinel")
        _repair_tenant(staging, "sentinel")
        assert "StrictModes no" not in _sshd_conf(staging)

    def test_cipher_snapshot_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/cipher_snapshot_desk.md").read_text(encoding="utf-8")
        assert "aes128-cbc" in desk
        staging = _fresh_staging("desk_cipher")
        _repair_tenant(staging, "cipher")
        assert "aes128-cbc" not in _sshd_conf(staging)


class TestCrossTenantIsolationRound8:
    @pytest.mark.parametrize(
        "left,right,left_marker,right_marker",
        [
            ("ember", "nexus", "Compression delayed", "ClientAliveInterval 120"),
            ("onyx", "rift", "PrintMotd no", "MaxSessions 4"),
            ("sentinel", "prism", "StrictModes yes", "LogLevel VERBOSE"),
            ("cipher", "quasar", "aes256-gcm@openssh.com", "PermitTTY no"),
        ],
    )
    def test_round6_and_legacy_sshd_directives_differ(
        self, left: str, right: str, left_marker: str, right_marker: str
    ) -> None:
        a = _fresh_staging(f"r8_{left}")
        b = _fresh_staging(f"r8_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert left_marker in _sshd_conf(a)
        assert right_marker in _sshd_conf(b)


class TestRepairSequenceDepthRound6:
    @pytest.mark.parametrize("tenant", ROUND6_HELD_OUT_TENANTS)
    def test_third_repair_still_noop(self, tenant: str) -> None:
        staging = _fresh_staging(f"r6_third_{tenant}")
        for idx in range(1, 3):
            _repair_tenant(staging, tenant, f"fix{idx}.json")
        manifest = _repair_tenant(staging, tenant, "fix3.json")
        assert manifest["noop"] is True

    @pytest.mark.parametrize("tenant", ROUND6_HELD_OUT_TENANTS)
    def test_first_and_second_manifest_hashes_differ_then_stable(
        self, tenant: str
    ) -> None:
        staging = _fresh_staging(f"r6_hash_{tenant}")
        first = _repair_tenant(staging, tenant, "fix1.json")
        second = _repair_tenant(staging, tenant, "fix2.json")
        assert first["manifest_sha256"] != second["manifest_sha256"]
        assert second["manifest_sha256"] == _manifest_hash([])


class TestHandbookAmendmentRound6:
    def test_handbook_amendment_2025_19_ember_onyx(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-19" in handbook
        assert "RULE:EMBER_TENANT=ember" in handbook
        assert "RULE:ONYX_TENANT=onyx" in handbook

    def test_handbook_amendment_2025_20_sentinel_cipher(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-20" in handbook
        assert "RULE:SENTINEL_TENANT=sentinel" in handbook
        assert "RULE:CIPHER_TENANT=cipher" in handbook

ROUND7_HELD_OUT_TENANTS = ["quartz", "obsidian", "garnet", "slate"]


class TestLayerExtractIdempotencyRoundS:
    """Layer 1: handbook Amendment 2025-21 extract marker idempotency."""

    def test_handbook_amendment_2025_21_extract_marker(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-21" in handbook
        assert "RULE:EXTRACT_MARKER=.bastion_extracted" in handbook
        assert "RULE:EXTRACT_POLICY=skip_when_marker_present" in handbook

    def test_extract_marker_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/extract_marker_desk.md").read_text(encoding="utf-8")
        assert "always_fresh" in desk
        staging = _fresh_staging("layer1_desk")
        _repair_tenant(staging, "prod")
        _audit_tenant(staging, "prod")
        assert _audit_tenant(staging, "prod")["clean"] is True

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_extract_marker_survives_repair_then_audit(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer1_marker_{tenant}")
        _repair_tenant(staging, tenant)
        marker = staging / "extracted/.bastion_extracted"
        assert marker.is_file(), tenant
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is True, tenant
        assert marker.is_file(), tenant


class TestLayerSshdGlobalBaselineRoundS:
    """Layer 2: handbook Amendment 2025-22 deep merge preserves global directives."""

    def test_handbook_amendment_2025_22_sshd_merge(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-22" in handbook
        assert "RULE:SSHD_MERGE=deep_per_directive_global_base" in handbook

    def test_sshd_replace_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/sshd_replace_desk.md").read_text(encoding="utf-8")
        assert "replace_file" in desk
        staging = _fresh_staging("layer2_desk")
        _repair_tenant(staging, "staging")
        conf = _sshd_conf(staging)
        assert "PermitRootLogin no" in conf
        assert "PasswordAuthentication no" in conf

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_global_password_authentication_no_preserved(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer2_pwd_{tenant}")
        _repair_tenant(staging, tenant)
        assert "PasswordAuthentication no" in _sshd_conf(staging)

    @pytest.mark.parametrize("tenant", [t for t in ALL_TENANTS if t != "prod"])
    def test_global_permit_root_login_no_when_not_overridden(
        self, tenant: str
    ) -> None:
        staging = _fresh_staging(f"layer2_root_{tenant}")
        _repair_tenant(staging, tenant)
        conf = _sshd_conf(staging)
        assert "PermitRootLogin no" in conf, tenant
        assert "prohibit-password" not in conf, tenant


class TestLayerAuditExitCodesRoundS:
    """Layer 3: handbook Amendment 2025-23 audit exit codes."""

    def test_handbook_amendment_2025_23_audit_exit(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-23" in handbook
        assert "RULE:AUDIT_EXIT_CLEAN=0" in handbook
        assert "RULE:AUDIT_EXIT_DIRTY=3" in handbook

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_pre_repair_audit_exits_dirty(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer3_dirty_{tenant}")
        report_path = staging / "pre.json"
        proc = _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                tenant,
                "--report",
                str(report_path),
            ],
            check=False,
        )
        assert proc.returncode == 3, tenant

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_post_repair_audit_exits_clean(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer3_clean_{tenant}")
        _repair_tenant(staging, tenant)
        report_path = staging / "post.json"
        proc = _run(
            [
                "audit",
                "--staging",
                str(staging),
                "--bundle",
                str(staging / "bundle.tar.gz"),
                "--tenant",
                tenant,
                "--report",
                str(report_path),
            ],
            check=False,
        )
        assert proc.returncode == 0, tenant


class TestLayerExtremeRepairAuditStressRoundS:
    """Layer 5: multi-step repair/audit chains and live registry mutation."""

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_four_step_repair_audit_chain(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer5_chain_{tenant}")
        _repair_tenant(staging, tenant, "fix1.json")
        assert _audit_tenant(staging, tenant, "audit1.json")["clean"] is True
        manifest = _repair_tenant(staging, tenant, "fix2.json")
        assert manifest["noop"] is True
        assert _audit_tenant(staging, tenant, "audit2.json")["clean"] is True

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_seventh_repair_still_noop(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer5_seventh_{tenant}")
        for idx in range(1, 7):
            _repair_tenant(staging, tenant, f"fix{idx}.json")
        manifest = _repair_tenant(staging, tenant, "fix7.json")
        assert manifest["noop"] is True
        assert manifest["changes"] == []

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_live_key_rotation_between_audits(self, tenant: str) -> None:
        staging = _fresh_staging(f"layer5_keyrot_{tenant}")
        _repair_tenant(staging, tenant)
        assert _audit_tenant(staging, tenant)["clean"] is True
        rotated = f"ssh-rsa LAYER5-{tenant.upper()} alice@corp"
        _redis_hset("bastion:ssh_keys", "alice", rotated)
        _repair_tenant(staging, tenant, "fix2.json")
        assert _audit_tenant(staging, tenant)["clean"] is True
        key = (
            staging / "extracted/homes/alice/.ssh/authorized_keys"
        ).read_text(encoding="utf-8").strip()
        assert key == rotated

    @pytest.mark.parametrize("left,right", [
        ("quartz", "obsidian"),
        ("garnet", "slate"),
        ("ember", "quartz"),
        ("prod", "garnet"),
    ])
    def test_round7_tenant_trees_remain_isolated(self, left: str, right: str) -> None:
        a = _fresh_staging(f"layer5_iso_{left}")
        b = _fresh_staging(f"layer5_iso_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert _audit_tenant(a, left)["clean"] is True
        assert _audit_tenant(b, right)["clean"] is True
        assert _sshd_conf(a) != _sshd_conf(b)



class TestHeldOutQuartzTenant:
    def test_quartz_overlay_applied(self) -> None:
        staging = _fresh_staging("quartz_overlay")
        _repair_tenant(staging, "quartz")
        conf = _sshd_conf(staging)
        assert "LoginGraceTime 30" in conf
        assert "LoginGraceTime 120" not in conf

    def test_quartz_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("quartz_cache")
        _repair_tenant(staging, "quartz")
        assert "LoginGraceTime 120" not in _sshd_conf(staging)

    def test_quartz_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("quartz_audit")
        _repair_tenant(staging, "quartz")
        report = _audit_tenant(staging, "quartz")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_quartz_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("quartz_digest")
        manifest = _repair_tenant(staging, "quartz")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_quartz_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("quartz_noop")
        _repair_tenant(staging, "quartz", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "quartz", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutObsidianTenant:
    def test_obsidian_overlay_applied(self) -> None:
        staging = _fresh_staging("obsidian_overlay")
        _repair_tenant(staging, "obsidian")
        conf = _sshd_conf(staging)
        assert "MaxStartups 10:30:60" in conf
        assert "MaxStartups 5:5:5" not in conf

    def test_obsidian_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("obsidian_cache")
        _repair_tenant(staging, "obsidian")
        assert "MaxStartups 5:5:5" not in _sshd_conf(staging)

    def test_obsidian_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("obsidian_audit")
        _repair_tenant(staging, "obsidian")
        report = _audit_tenant(staging, "obsidian")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_obsidian_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("obsidian_digest")
        manifest = _repair_tenant(staging, "obsidian")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_obsidian_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("obsidian_noop")
        _repair_tenant(staging, "obsidian", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "obsidian", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutGarnetTenant:
    def test_garnet_overlay_applied(self) -> None:
        staging = _fresh_staging("garnet_overlay")
        _repair_tenant(staging, "garnet")
        conf = _sshd_conf(staging)
        assert "AllowAgentForwarding no" in conf
        assert "AllowAgentForwarding yes" not in conf

    def test_garnet_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("garnet_cache")
        _repair_tenant(staging, "garnet")
        assert "AllowAgentForwarding yes" not in _sshd_conf(staging)

    def test_garnet_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("garnet_audit")
        _repair_tenant(staging, "garnet")
        report = _audit_tenant(staging, "garnet")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_garnet_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("garnet_digest")
        manifest = _repair_tenant(staging, "garnet")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_garnet_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("garnet_noop")
        _repair_tenant(staging, "garnet", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "garnet", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutSlateTenant:
    def test_slate_overlay_applied(self) -> None:
        staging = _fresh_staging("slate_overlay")
        _repair_tenant(staging, "slate")
        conf = _sshd_conf(staging)
        assert "AllowTcpForwarding no" in conf
        assert "AllowTcpForwarding yes" not in conf

    def test_slate_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("slate_cache")
        _repair_tenant(staging, "slate")
        assert "AllowTcpForwarding yes" not in _sshd_conf(staging)

    def test_slate_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("slate_audit")
        _repair_tenant(staging, "slate")
        report = _audit_tenant(staging, "slate")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_slate_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("slate_digest")
        manifest = _repair_tenant(staging, "slate")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_slate_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("slate_noop")
        _repair_tenant(staging, "slate", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "slate", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest


class TestDeepHardeningRoundN:
    def test_quartz_and_ember_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundn_quartz")
        b = _fresh_staging("roundn_ember")
        _repair_tenant(a, "quartz")
        _repair_tenant(b, "ember")
        assert "LoginGraceTime 30" in _sshd_conf(a)
        assert "Compression delayed" in _sshd_conf(b)

    def test_obsidian_and_onyx_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundn_obsidian")
        b = _fresh_staging("roundn_onyx")
        _repair_tenant(a, "obsidian")
        _repair_tenant(b, "onyx")
        assert "MaxStartups 10:30:60" in _sshd_conf(a)
        assert "PrintMotd no" in _sshd_conf(b)

    def test_garnet_and_sentinel_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundn_garnet")
        b = _fresh_staging("roundn_sentinel")
        _repair_tenant(a, "garnet")
        _repair_tenant(b, "sentinel")
        assert "AllowAgentForwarding no" in _sshd_conf(a)
        assert "StrictModes yes" in _sshd_conf(b)

    def test_slate_and_cipher_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundn_slate")
        b = _fresh_staging("roundn_cipher")
        _repair_tenant(a, "slate")
        _repair_tenant(b, "cipher")
        assert "AllowTcpForwarding no" in _sshd_conf(a)
        assert "Ciphers aes256-gcm@openssh.com" in _sshd_conf(b)


class TestDeskTrapBehavioralRound9:
    def test_quartz_cache_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_quartz")
        _repair_tenant(staging, "quartz")
        assert "LoginGraceTime 120" not in _sshd_conf(staging)

    def test_obsidian_alias_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_obsidian")
        _repair_tenant(staging, "obsidian")
        assert "MaxStartups 5:5:5" not in _sshd_conf(staging)

    def test_garnet_global_first_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_garnet")
        _repair_tenant(staging, "garnet")
        assert "AllowAgentForwarding yes" not in _sshd_conf(staging)

    def test_slate_snapshot_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_slate")
        _repair_tenant(staging, "slate")
        assert "AllowTcpForwarding yes" not in _sshd_conf(staging)


class TestHandbookAmendmentRound7:
    def test_handbook_amendment_2025_24_quartz_obsidian(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-24" in handbook
        assert "RULE:QUARTZ_TENANT=quartz" in handbook
        assert "RULE:OBSIDIAN_TENANT=obsidian" in handbook

    def test_handbook_amendment_2025_25_garnet_slate(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-25" in handbook
        assert "RULE:GARNET_TENANT=garnet" in handbook
        assert "RULE:SLATE_TENANT=slate" in handbook

ROUND8_HELD_OUT_TENANTS = ["crimson", "jade", "opal", "ivory"]


class TestTagReviewRoundT:
    """Tag-review compensation: manifest path normalization + round-8 tenants."""

    def test_handbook_amendment_2025_28_manifest_paths(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-28" in handbook
        assert "RULE:MANIFEST_PATHS=relative_no_leading_dot_slash" in handbook

    def test_manifest_dot_slash_desk_is_decoy(self) -> None:
        desk = Path("/app/docs/manifest_dot_slash_desk.md").read_text(encoding="utf-8")
        assert "./" in desk
        staging = _fresh_staging("tagreview_desk")
        manifest = _repair_tenant(staging, "prod")
        for change in manifest["changes"]:
            assert not change["path"].startswith("./")

    @pytest.mark.parametrize("tenant", ALL_TENANTS)
    def test_manifest_paths_have_no_dot_slash_prefix(self, tenant: str) -> None:
        staging = _fresh_staging(f"tagreview_path_{tenant}")
        manifest = _repair_tenant(staging, tenant)
        for change in manifest["changes"]:
            assert not change["path"].startswith("./"), tenant
            assert change["path"] == change["path"].lstrip("/"), tenant

    @pytest.mark.parametrize("tenant", ROUND8_HELD_OUT_TENANTS)
    def test_round8_tenant_post_repair_audit_clean(self, tenant: str) -> None:
        staging = _fresh_staging(f"tagreview_clean_{tenant}")
        _repair_tenant(staging, tenant)
        report = _audit_tenant(staging, tenant)
        assert report["clean"] is True, tenant

    @pytest.mark.parametrize("tenant", ROUND8_HELD_OUT_TENANTS)
    def test_round8_fifth_repair_noop(self, tenant: str) -> None:
        staging = _fresh_staging(f"tagreview_noop5_{tenant}")
        for idx in range(4):
            manifest = _repair_tenant(staging, tenant, f"fix{idx}.json")
            if idx > 0:
                assert manifest["noop"] is True, tenant


class TestDeskTrapBehavioralRound10:
    def test_crimson_cache_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_crimson")
        _repair_tenant(staging, "crimson")
        assert "ClientAliveInterval 60" not in _sshd_conf(staging)

    def test_jade_alias_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_jade")
        _repair_tenant(staging, "jade")
        assert "MaxAuthTries 6" not in _sshd_conf(staging)

    def test_opal_global_first_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_opal")
        _repair_tenant(staging, "opal")
        assert "X11Forwarding yes" not in _sshd_conf(staging)

    def test_ivory_snapshot_desk_is_decoy(self) -> None:
        staging = _fresh_staging("desk_ivory")
        _repair_tenant(staging, "ivory")
        assert "AllowStreamLocalForwarding yes" not in _sshd_conf(staging)


class TestDeepHardeningRoundO:
    def test_crimson_and_jade_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundo_crimson")
        b = _fresh_staging("roundo_jade")
        _repair_tenant(a, "crimson")
        _repair_tenant(b, "jade")
        assert "ClientAliveInterval 300" in _sshd_conf(a)
        assert "MaxAuthTries 3" in _sshd_conf(b)

    def test_opal_and_ivory_repairs_remain_distinct(self) -> None:
        a = _fresh_staging("roundo_opal")
        b = _fresh_staging("roundo_ivory")
        _repair_tenant(a, "opal")
        _repair_tenant(b, "ivory")
        assert "X11Forwarding no" in _sshd_conf(a)
        assert "AllowStreamLocalForwarding no" in _sshd_conf(b)

    @pytest.mark.parametrize("left,right", [("crimson", "jade"), ("opal", "ivory")])
    def test_round8_pair_isolation(self, left: str, right: str) -> None:
        a = _fresh_staging(f"roundo_iso_{left}")
        b = _fresh_staging(f"roundo_iso_{right}")
        _repair_tenant(a, left)
        _repair_tenant(b, right)
        assert _sshd_conf(a) != _sshd_conf(b)


class TestHandbookAmendmentRound8:
    def test_handbook_amendment_2025_26_crimson_jade(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-26" in handbook
        assert "RULE:CRIMSON_TENANT=crimson" in handbook
        assert "RULE:JADE_TENANT=jade" in handbook

    def test_handbook_amendment_2025_27_opal_ivory(self) -> None:
        handbook = Path("/app/docs/bastion_access_handbook.md").read_text(
            encoding="utf-8"
        )
        assert "Amendment 2025-27" in handbook
        assert "RULE:OPAL_TENANT=opal" in handbook
        assert "RULE:IVORY_TENANT=ivory" in handbook



class TestHeldOutCrimsonTenant:
    def test_crimson_overlay_applied(self) -> None:
        staging = _fresh_staging("crimson_overlay")
        _repair_tenant(staging, "crimson")
        conf = _sshd_conf(staging)
        assert "ClientAliveInterval 300" in conf
        assert "ClientAliveInterval 60" not in conf

    def test_crimson_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("crimson_cache")
        _repair_tenant(staging, "crimson")
        assert "ClientAliveInterval 60" not in _sshd_conf(staging)

    def test_crimson_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("crimson_audit")
        _repair_tenant(staging, "crimson")
        report = _audit_tenant(staging, "crimson")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_crimson_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("crimson_digest")
        manifest = _repair_tenant(staging, "crimson")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_crimson_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("crimson_noop")
        _repair_tenant(staging, "crimson", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "crimson", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutJadeTenant:
    def test_jade_overlay_applied(self) -> None:
        staging = _fresh_staging("jade_overlay")
        _repair_tenant(staging, "jade")
        conf = _sshd_conf(staging)
        assert "MaxAuthTries 3" in conf
        assert "MaxAuthTries 6" not in conf

    def test_jade_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("jade_cache")
        _repair_tenant(staging, "jade")
        assert "MaxAuthTries 6" not in _sshd_conf(staging)

    def test_jade_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("jade_audit")
        _repair_tenant(staging, "jade")
        report = _audit_tenant(staging, "jade")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_jade_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("jade_digest")
        manifest = _repair_tenant(staging, "jade")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_jade_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("jade_noop")
        _repair_tenant(staging, "jade", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "jade", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutOpalTenant:
    def test_opal_overlay_applied(self) -> None:
        staging = _fresh_staging("opal_overlay")
        _repair_tenant(staging, "opal")
        conf = _sshd_conf(staging)
        assert "X11Forwarding no" in conf
        assert "X11Forwarding yes" not in conf

    def test_opal_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("opal_cache")
        _repair_tenant(staging, "opal")
        assert "X11Forwarding yes" not in _sshd_conf(staging)

    def test_opal_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("opal_audit")
        _repair_tenant(staging, "opal")
        report = _audit_tenant(staging, "opal")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_opal_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("opal_digest")
        manifest = _repair_tenant(staging, "opal")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_opal_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("opal_noop")
        _repair_tenant(staging, "opal", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "opal", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest



class TestHeldOutIvoryTenant:
    def test_ivory_overlay_applied(self) -> None:
        staging = _fresh_staging("ivory_overlay")
        _repair_tenant(staging, "ivory")
        conf = _sshd_conf(staging)
        assert "AllowStreamLocalForwarding no" in conf
        assert "AllowStreamLocalForwarding yes" not in conf

    def test_ivory_ignores_seeded_registry_cache(self) -> None:
        staging = _fresh_staging("ivory_cache")
        _repair_tenant(staging, "ivory")
        assert "AllowStreamLocalForwarding yes" not in _sshd_conf(staging)

    def test_ivory_tenant_audit_clean_after_repair(self) -> None:
        staging = _fresh_staging("ivory_audit")
        _repair_tenant(staging, "ivory")
        report = _audit_tenant(staging, "ivory")
        assert report["clean"] is True
        assert report["violations"] == []

    def test_ivory_manifest_digest_matches_sorted_changes(self) -> None:
        staging = _fresh_staging("ivory_digest")
        manifest = _repair_tenant(staging, "ivory")
        assert manifest["manifest_sha256"] == _manifest_hash(manifest["changes"])

    def test_ivory_second_repair_noop_preserves_files(self) -> None:
        staging = _fresh_staging("ivory_noop")
        _repair_tenant(staging, "ivory", "fix1.json")
        tracked = staging / "extracted/ssh/sshd_config.d/bastion.conf"
        digest = _sha256_file(tracked)
        manifest = _repair_tenant(staging, "ivory", "fix2.json")
        assert manifest["noop"] is True
        assert _sha256_file(tracked) == digest
