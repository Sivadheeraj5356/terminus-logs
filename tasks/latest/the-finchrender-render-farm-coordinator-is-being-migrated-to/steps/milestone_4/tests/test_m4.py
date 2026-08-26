import json
import os
import re
import subprocess

import pytest

OUTPUT = "/app/output"
AUDIT = os.path.join(OUTPUT, "syscall-audit.json")
SYSCTL = os.path.join(OUTPUT, "99-finchrender-shmmax.conf")
DROPIN = os.path.join(OUTPUT, "finchrender-drop-in.conf")
AUDIT_FILES = ["syscall-audit.json", "99-finchrender-shmmax.conf", "finchrender-drop-in.conf"]


@pytest.fixture(scope="module", autouse=True)
def run_audit():
    """Clear prior output and re-run the audit CLI so tests check the actual command."""
    for name in AUDIT_FILES:
        path = os.path.join(OUTPUT, name)
        if os.path.exists(path):
            os.remove(path)
    return subprocess.run(
        ["npx", "--yes", "ts-node", "src/cli.ts", "audit"],
        cwd="/app",
        capture_output=True,
        text=True,
    )


def load_audit():
    with open(AUDIT) as f:
        return json.load(f)


class TestMilestone4:
    def test_audit_command_succeeds(self, run_audit):
        """npx ts-node /app/src/cli.ts audit must exit zero."""
        assert run_audit.returncode == 0, run_audit.stderr

    def test_audit_exists(self):
        """syscall-audit.json must be created by the audit command."""
        assert os.path.isfile(AUDIT)

    def test_audit_valid_json(self):
        """syscall-audit.json must be valid JSON with required top-level keys."""
        data = load_audit()
        assert isinstance(data, dict)
        assert "syscalls_observed" in data
        assert "extra_syscalls" in data
        assert "sysctl_required" in data

    def test_syscalls_observed_is_list(self):
        """syscalls_observed must be a non-empty list."""
        data = load_audit()
        obs = data.get("syscalls_observed", [])
        assert isinstance(obs, list)
        assert len(obs) > 10

    def test_syscalls_observed_sorted(self):
        """syscalls_observed must be sorted alphabetically."""
        data = load_audit()
        obs = data.get("syscalls_observed", [])
        assert obs == sorted(obs), "syscalls_observed is not sorted"

    def test_syscalls_observed_no_duplicates(self):
        """syscalls_observed must contain no duplicate entries."""
        data = load_audit()
        obs = data.get("syscalls_observed", [])
        assert len(obs) == len(set(obs)), "syscalls_observed has duplicates"

    def test_cold_startup_syscalls_present(self):
        """Core syscalls from startup-cold.strace must appear in syscalls_observed."""
        data = load_audit()
        observed = set(data.get("syscalls_observed", []))
        for sc in ["execve", "capset", "setuid", "setgid", "bind", "openat", "epoll_create1", "prctl"]:
            assert sc in observed, f"Missing syscall from cold startup: {sc}"

    def test_reload_syscalls_present(self):
        """Syscalls unique to graceful-reload.strace must also appear (clone, waitpid, exit_group)."""
        data = load_audit()
        observed = set(data.get("syscalls_observed", []))
        for sc in ["clone", "waitpid", "exit_group"]:
            assert sc in observed, f"Missing syscall from graceful-reload trace: {sc}"

    def test_extra_syscalls_contains_cap_calls(self):
        """extra_syscalls must include capget, capset, prctl (not covered by @system-service)."""
        data = load_audit()
        extra = set(data.get("extra_syscalls", []))
        assert "capget" in extra, "capget must be in extra_syscalls"
        assert "capset" in extra, "capset must be in extra_syscalls"
        assert "prctl" in extra, "prctl must be in extra_syscalls"

    def test_extra_syscalls_excludes_setuid_setgid(self):
        """setuid and setgid must NOT appear in extra_syscalls (systemd User= makes them no-ops)."""
        data = load_audit()
        extra = set(data.get("extra_syscalls", []))
        assert "setuid" not in extra, "setuid must not be in extra_syscalls (systemd handles uid)"
        assert "setgid" not in extra, "setgid must not be in extra_syscalls (systemd handles gid)"

    def test_sysctl_required_shmmax(self):
        """sysctl_required must contain kernel.shmmax = 67108864."""
        data = load_audit()
        sysctl = data.get("sysctl_required", {})
        assert sysctl.get("kernel.shmmax") == "67108864", (
            f"kernel.shmmax must be '67108864', got {sysctl.get('kernel.shmmax')!r}"
        )

    def test_sysctl_conf_exists(self):
        """99-finchrender-shmmax.conf must be created by the audit command."""
        assert os.path.isfile(SYSCTL)

    def test_sysctl_conf_content(self):
        """sysctl.d file must contain a real (non-comment) assignment line
        setting kernel.shmmax to 67108864 — not merely mentioned in a comment."""
        with open(SYSCTL) as f:
            lines = f.readlines()
        assignment_lines = [
            ln for ln in lines
            if not ln.strip().startswith("#") and re.match(r"^\s*kernel\.shmmax\s*=\s*67108864\s*$", ln)
        ]
        assert assignment_lines, (
            f"No non-comment 'kernel.shmmax = 67108864' assignment line found in {SYSCTL}"
        )

    def test_dropin_exists(self):
        """finchrender-drop-in.conf must be created by the audit command."""
        assert os.path.isfile(DROPIN)

    def test_dropin_service_section(self):
        """Drop-in must contain a [Service] section header."""
        with open(DROPIN) as f:
            content = f.read()
        assert "[Service]" in content

    def _dropin_filter_lines(self):
        with open(DROPIN) as f:
            content = f.read()
        return [ln.strip() for ln in content.splitlines() if ln.strip().startswith("SystemCallFilter=")]

    def test_dropin_system_service_group(self):
        """Drop-in must have a standalone SystemCallFilter=@system-service line."""
        filter_lines = self._dropin_filter_lines()
        assert "SystemCallFilter=@system-service" in filter_lines, (
            f"Expected a standalone 'SystemCallFilter=@system-service' line, got: {filter_lines!r}"
        )

    def test_dropin_extra_syscalls(self):
        """Drop-in must have a SEPARATE second SystemCallFilter= line (not merged with
        @system-service) whose tokens are exactly capget, capset, prctl."""
        filter_lines = self._dropin_filter_lines()
        assert len(filter_lines) >= 2, (
            f"Expected two distinct SystemCallFilter= lines, got: {filter_lines!r}"
        )
        extra_line = next(
            (ln for ln in filter_lines if ln != "SystemCallFilter=@system-service"), ""
        )
        assert extra_line, "second SystemCallFilter= line (extra syscalls) not found"
        assert "@system-service" not in extra_line, (
            f"@system-service must not be merged into the extra-syscalls line: {extra_line!r}"
        )
        extra_tokens = set(extra_line[len("SystemCallFilter="):].split())
        assert extra_tokens == {"capget", "capset", "prctl"}, (
            f"Expected extra SystemCallFilter tokens {{capget, capset, prctl}}, got {extra_tokens!r}"
        )

    def test_dropin_limit_nofile(self):
        """Drop-in must set LimitNOFILE=64."""
        with open(DROPIN) as f:
            content = f.read()
        assert "LimitNOFILE=64" in content
