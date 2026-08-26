"""Verifies the generate CLI produces a correctly hardened systemd service unit, socket, tmpfiles, and env file."""
import os
import re
import subprocess

import pytest

OUTPUT = "/app/output"
GENERATED_FILES = [
    "finchrender.service",
    "finchrender.socket",
    "finchrender-tmpfiles.conf",
    "finchrender.env",
]


@pytest.fixture(scope="module", autouse=True)
def run_generate():
    """Clear prior output and re-run the generate CLI so tests check the actual command."""
    for name in GENERATED_FILES:
        path = os.path.join(OUTPUT, name)
        if os.path.exists(path):
            os.remove(path)
    return subprocess.run(
        ["npx", "--yes", "ts-node", "src/cli.ts", "generate"],
        cwd="/app",
        capture_output=True,
        text=True,
    )


def read_file(name):
    with open(os.path.join(OUTPUT, name)) as f:
        return f.read()


def get_directive_text(content, prefix):
    """Return the joined text of all lines starting with prefix — systemd directives like
    ReadWritePaths=/After= are cumulative across repeated lines, not overriding."""
    lines = [line.strip() for line in content.splitlines() if line.strip().startswith(prefix)]
    return " ".join(lines)


class TestMilestone2:
    def test_generate_command_succeeds(self, run_generate):
        """npx ts-node /app/src/cli.ts generate must exit zero."""
        assert run_generate.returncode == 0, run_generate.stderr

    def test_service_exists(self):
        """finchrender.service must be created by the generate command."""
        assert os.path.isfile(os.path.join(OUTPUT, "finchrender.service"))

    def test_socket_exists(self):
        """finchrender.socket must be created by the generate command."""
        assert os.path.isfile(os.path.join(OUTPUT, "finchrender.socket"))

    def test_tmpfiles_exists(self):
        """finchrender-tmpfiles.conf must be created by the generate command."""
        assert os.path.isfile(os.path.join(OUTPUT, "finchrender-tmpfiles.conf"))

    def test_envfile_exists(self):
        """finchrender.env must be created by the generate command."""
        assert os.path.isfile(os.path.join(OUTPUT, "finchrender.env"))

    def test_service_user_group(self):
        """Service unit must set User=finchrender and Group=render."""
        content = read_file("finchrender.service")
        assert "User=finchrender" in content
        assert "Group=render" in content

    def test_no_new_privileges(self):
        """Service unit must set NoNewPrivileges=yes."""
        content = read_file("finchrender.service")
        assert "NoNewPrivileges=yes" in content

    def test_private_tmp(self):
        """Service unit must set PrivateTmp=yes."""
        content = read_file("finchrender.service")
        assert "PrivateTmp=yes" in content

    def test_capability_bounding(self):
        """CapabilityBoundingSet must include both required capabilities."""
        content = read_file("finchrender.service")
        cap_line = next(
            (line for line in content.splitlines() if "CapabilityBoundingSet" in line), ""
        )
        assert "CAP_SYS_NICE" in cap_line
        assert "CAP_NET_BIND_SERVICE" in cap_line

    def test_ambient_capabilities(self):
        """AmbientCapabilities must include both required capabilities."""
        content = read_file("finchrender.service")
        amb_line = next(
            (line for line in content.splitlines() if "AmbientCapabilities" in line), ""
        )
        assert amb_line, "AmbientCapabilities= directive not found in finchrender.service"
        assert "CAP_SYS_NICE" in amb_line
        assert "CAP_NET_BIND_SERVICE" in amb_line

    def test_environment_file(self):
        """EnvironmentFile= must point at the coordinator's env file exactly."""
        content = read_file("finchrender.service")
        env_line = next(
            (line.strip() for line in content.splitlines() if line.strip().startswith("EnvironmentFile=")), ""
        )
        assert env_line == "EnvironmentFile=/etc/finchrender/finchrender.env", (
            f"Expected EnvironmentFile=/etc/finchrender/finchrender.env, got {env_line!r}"
        )

    def test_udev_settle_after(self):
        """After= must include udev-settle.service for reliable GPU enumeration."""
        content = read_file("finchrender.service")
        after_text = get_directive_text(content, "After=")
        assert "udev-settle.service" in after_text, (
            "After= must include udev-settle.service (see ops dossier incident history)"
        )

    def test_start_limit_burst(self):
        """StartLimitBurst=5 must be set per the restart policy in the ops dossier."""
        content = read_file("finchrender.service")
        assert "StartLimitBurst=5" in content

    def test_start_limit_interval(self):
        """StartLimitIntervalSec=10min must be set per the restart policy in the ops dossier."""
        content = read_file("finchrender.service")
        assert "StartLimitIntervalSec=10min" in content

    def test_limit_nofile(self):
        """LimitNOFILE=64 must be set to provide a tight fd ceiling above observed max."""
        content = read_file("finchrender.service")
        assert "LimitNOFILE=64" in content

    def test_readwrite_paths_cache(self):
        """ReadWritePaths= must include /var/cache/finchrender for the cache directories."""
        content = read_file("finchrender.service")
        rw_text = get_directive_text(content, "ReadWritePaths=")
        assert rw_text, "ReadWritePaths= directive not found in finchrender.service"
        assert "/var/cache/finchrender" in rw_text, (
            f"ReadWritePaths= does not include /var/cache/finchrender: {rw_text!r}"
        )

    def test_readwrite_paths_log(self):
        """ReadWritePaths= must include /var/log/finchrender for the log directory."""
        content = read_file("finchrender.service")
        rw_text = get_directive_text(content, "ReadWritePaths=")
        assert rw_text, "ReadWritePaths= directive not found in finchrender.service"
        assert "/var/log/finchrender" in rw_text, (
            f"ReadWritePaths= does not include /var/log/finchrender: {rw_text!r}"
        )

    def test_readwrite_paths_checkpoint(self):
        """ReadWritePaths= must include /var/lib/finchrender for the checkpoint directory."""
        content = read_file("finchrender.service")
        rw_text = get_directive_text(content, "ReadWritePaths=")
        assert rw_text, "ReadWritePaths= directive not found in finchrender.service"
        assert "/var/lib/finchrender" in rw_text, (
            f"ReadWritePaths= does not include /var/lib/finchrender: {rw_text!r}"
        )

    def test_syscall_filter_system_service(self):
        """Service unit must include SystemCallFilter=@system-service."""
        content = read_file("finchrender.service")
        assert "SystemCallFilter=@system-service" in content

    def test_syscall_filter_extra_caps(self):
        """Service unit must add capget, capset, prctl to SystemCallFilter for cap management."""
        content = read_file("finchrender.service")
        filter_lines = [ln.strip() for ln in content.splitlines() if "SystemCallFilter" in ln]
        all_filter = " ".join(filter_lines)
        assert "capget" in all_filter
        assert "capset" in all_filter
        assert "prctl" in all_filter

    def test_socket_listen_stream(self):
        """Socket unit must set ListenStream to the coordinator socket path."""
        content = read_file("finchrender.socket")
        assert "ListenStream=/run/finchrender/coordinator.sock" in content

    def test_tmpfiles_run_dir(self):
        """tmpfiles.conf must have a d entry for /run/finchrender."""
        content = read_file("finchrender-tmpfiles.conf")
        assert re.search(r"^d\s+/run/finchrender", content, re.MULTILINE)

    def test_tmpfiles_cache_tiles(self):
        """tmpfiles.conf must have an entry for /var/cache/finchrender/tiles."""
        content = read_file("finchrender-tmpfiles.conf")
        assert "/var/cache/finchrender/tiles" in content

    def test_tmpfiles_cache_frames(self):
        """tmpfiles.conf must have an entry for /var/cache/finchrender/frames."""
        content = read_file("finchrender-tmpfiles.conf")
        assert "/var/cache/finchrender/frames" in content

    def test_tmpfiles_cache_shaders(self):
        """tmpfiles.conf must have an entry for /var/cache/finchrender/shaders."""
        content = read_file("finchrender-tmpfiles.conf")
        assert "/var/cache/finchrender/shaders" in content

    def test_env_vars(self):
        """finchrender.env must contain all four FINCHRENDER_* variables."""
        content = read_file("finchrender.env")
        assert "FINCHRENDER_TILE_WORKERS=8" in content
        assert "FINCHRENDER_FRAME_BUFFER_MB=512" in content
        assert "FINCHRENDER_SOCKET_TIMEOUT=30" in content
        assert "FINCHRENDER_LOG_LEVEL=info" in content

    def test_gpu_device_allow(self):
        """DeviceAllow entry for /dev/dri/renderD128 must grant exactly rw access."""
        content = read_file("finchrender.service")
        dev_line = next(
            (line.strip() for line in content.splitlines() if "DeviceAllow" in line and "/dev/dri/renderD128" in line),
            "",
        )
        assert dev_line, "DeviceAllow= entry for /dev/dri/renderD128 not found in finchrender.service"
        assert dev_line == "DeviceAllow=/dev/dri/renderD128 rw", (
            f"Expected DeviceAllow=/dev/dri/renderD128 rw, got {dev_line!r}"
        )
