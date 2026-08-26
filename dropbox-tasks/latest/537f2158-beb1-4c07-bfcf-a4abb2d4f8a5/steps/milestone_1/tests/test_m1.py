import glob
import json
import os

CONTRACTS = "/app/output/contracts.json"
TRACES_DIR = "/app/traces"


def load_contracts():
    with open(CONTRACTS) as f:
        return json.load(f)


def expected_syscall_set():
    """Independently re-derive the full deduplicated syscall inventory from the raw
    .strace fixtures, so completeness is checked against ground truth, not trusted."""
    names = set()
    for path in glob.glob(os.path.join(TRACES_DIR, "*.strace")):
        with open(path) as f:
            for line in f:
                t = line.strip()
                if not t or t.startswith("#") or t.startswith("+++") or t.startswith("---"):
                    continue
                if "<unfinished" in t or "resumed>" in t:
                    continue
                if "(" not in t:
                    continue
                name = t.split("(", 1)[0].strip()
                if name and " " not in name:
                    names.add(name)
    return names


class TestMilestone1:
    def test_contracts_file_exists(self):
        """contracts.json must be created by the extract command."""
        assert os.path.isfile(CONTRACTS)

    def test_valid_json(self):
        """contracts.json must be valid JSON."""
        data = load_contracts()
        assert isinstance(data, dict)

    def test_user_and_group(self):
        """user must be 'finchrender' and group must be 'render'."""
        data = load_contracts()
        assert data.get("user") == "finchrender"
        assert data.get("group") == "render"

    def test_socket_path(self):
        """The coordinator UNIX socket path must be present in sockets."""
        data = load_contracts()
        assert "/run/finchrender/coordinator.sock" in data.get("sockets", [])

    def test_capabilities_exact(self):
        """Capabilities must be exactly CAP_SYS_NICE and CAP_NET_BIND_SERVICE."""
        data = load_contracts()
        caps = set(data.get("capabilities", []))
        assert caps == {"CAP_SYS_NICE", "CAP_NET_BIND_SERVICE"}

    def test_capabilities_excludes_predrop(self):
        """Pre-drop capabilities like CAP_CHOWN and CAP_DAC_OVERRIDE must NOT appear."""
        data = load_contracts()
        caps = set(data.get("capabilities", []))
        assert "CAP_CHOWN" not in caps
        assert "CAP_DAC_OVERRIDE" not in caps
        assert "CAP_SETUID" not in caps

    def test_cache_directories(self):
        """All three cache directories must be present."""
        data = load_contracts()
        cache_dirs = data.get("cache_dirs", [])
        assert "/var/cache/finchrender/tiles" in cache_dirs
        assert "/var/cache/finchrender/frames" in cache_dirs
        assert "/var/cache/finchrender/shaders" in cache_dirs

    def test_checkpoint_dir(self):
        """checkpoint_dir must be set to the value from coordinator.yaml checkpoints.dir."""
        data = load_contracts()
        assert data.get("checkpoint_dir") == "/var/lib/finchrender/checkpoints"

    def test_env_vars(self):
        """All four FINCHRENDER_* env vars must be present with correct values."""
        data = load_contracts()
        env = data.get("env_vars", {})
        assert env.get("FINCHRENDER_TILE_WORKERS") == "8"
        assert env.get("FINCHRENDER_FRAME_BUFFER_MB") == "512"
        assert env.get("FINCHRENDER_SOCKET_TIMEOUT") == "30"
        assert env.get("FINCHRENDER_LOG_LEVEL") == "info"

    def test_env_vars_no_non_finchrender(self):
        """env_vars must contain only FINCHRENDER_* keys — not PATH, HOME, USER, LISTEN_*."""
        data = load_contracts()
        env = data.get("env_vars", {})
        for key in env:
            assert key.startswith("FINCHRENDER_"), f"Non-FINCHRENDER_ key in env_vars: {key}"

    def test_policy_exceptions_minimum(self):
        """At least 3 policy exceptions must be present."""
        data = load_contracts()
        exceptions = data.get("policy_exceptions", [])
        assert len(exceptions) >= 3

    def test_shmmax_exception(self):
        """The /proc/sys/kernel/shmmax path must be in policy exceptions."""
        data = load_contracts()
        paths = [e.get("path", "") for e in data.get("policy_exceptions", [])]
        assert "/proc/sys/kernel/shmmax" in paths

    def test_gpu_exception(self):
        """The /dev/dri/renderD128 path must be in policy exceptions."""
        data = load_contracts()
        paths = [e.get("path", "") for e in data.get("policy_exceptions", [])]
        assert "/dev/dri/renderD128" in paths

    def test_gpu_exception_access_rw(self):
        """/dev/dri/renderD128 policy exception must have access='rw' (read-write device)."""
        data = load_contracts()
        gpu_exc = next(
            (e for e in data.get("policy_exceptions", []) if e.get("path") == "/dev/dri/renderD128"),
            None,
        )
        assert gpu_exc is not None, "/dev/dri/renderD128 exception not found"
        assert gpu_exc.get("access") == "rw", (
            f"Expected access='rw' for /dev/dri/renderD128, got {gpu_exc.get('access')!r}"
        )

    def test_shmmax_exception_access_read(self):
        """/proc/sys/kernel/shmmax policy exception must have access='read' (read-only proc file)."""
        data = load_contracts()
        shmmax_exc = next(
            (e for e in data.get("policy_exceptions", []) if e.get("path") == "/proc/sys/kernel/shmmax"),
            None,
        )
        assert shmmax_exc is not None, "/proc/sys/kernel/shmmax exception not found"
        assert shmmax_exc.get("access") == "read", (
            f"Expected access='read' for /proc/sys/kernel/shmmax, got {shmmax_exc.get('access')!r}"
        )

    def test_drm_exception(self):
        """The /sys/class/drm path must be in policy exceptions."""
        data = load_contracts()
        paths = [e.get("path", "") for e in data.get("policy_exceptions", [])]
        assert "/sys/class/drm" in paths

    def test_drm_exception_access_read(self):
        """/sys/class/drm policy exception must have access='read' (read-only sysfs enumeration)."""
        data = load_contracts()
        drm_exc = next(
            (e for e in data.get("policy_exceptions", []) if e.get("path") == "/sys/class/drm"),
            None,
        )
        assert drm_exc is not None, "/sys/class/drm exception not found"
        assert drm_exc.get("access") == "read", (
            f"Expected access='read' for /sys/class/drm, got {drm_exc.get('access')!r}"
        )

    def test_policy_exceptions_have_rationale(self):
        """Every policy exception must have a non-empty rationale string."""
        data = load_contracts()
        for exc in data.get("policy_exceptions", []):
            rationale = exc.get("rationale", "")
            assert rationale, f"Missing or empty rationale for path {exc.get('path')!r}"

    def test_fd_count_exact(self):
        """fd_count_observed must equal 15 (numeric fds 0-14 counted from under-load.lsof)."""
        data = load_contracts()
        assert data.get("fd_count_observed") == 15, (
            f"Expected fd_count_observed=15, got {data.get('fd_count_observed')}"
        )

    def test_syscall_set_present(self):
        """syscall_set must be a non-empty list."""
        data = load_contracts()
        sc = data.get("syscall_set", [])
        assert isinstance(sc, list)
        assert len(sc) > 10

    def test_syscall_set_sorted(self):
        """syscall_set must be sorted alphabetically."""
        data = load_contracts()
        sc = data.get("syscall_set", [])
        assert sc == sorted(sc), "syscall_set is not sorted"

    def test_syscall_set_complete(self):
        """syscall_set must be the exact deduplicated syscall inventory across ALL
        .strace files — not a superset/subset built from a partial sample."""
        data = load_contracts()
        observed = set(data.get("syscall_set", []))
        expected = expected_syscall_set()
        missing = expected - observed
        extra = observed - expected
        assert not missing, f"syscall_set is missing syscalls present in the traces: {sorted(missing)}"
        assert not extra, f"syscall_set contains syscalls not present in any trace: {sorted(extra)}"

    def test_syscall_set_no_duplicates(self):
        """syscall_set must contain no duplicate entries."""
        data = load_contracts()
        sc = data.get("syscall_set", [])
        assert len(sc) == len(set(sc)), "syscall_set contains duplicates"
