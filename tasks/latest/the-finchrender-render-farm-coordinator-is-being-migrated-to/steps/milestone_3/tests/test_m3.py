import json
import os
import subprocess

REPORT = "/app/output/validation-report.json"
SERVICE = "/app/output/finchrender.service"


def load_report():
    with open(REPORT) as f:
        return json.load(f)


def rerun_validate():
    subprocess.run(
        ["npx", "--yes", "ts-node", "src/cli.ts", "validate"],
        cwd="/app",
        capture_output=True,
        check=False,
    )
    return load_report()


class TestMilestone3:
    def test_report_exists(self):
        """validation-report.json must be created by the validate command."""
        assert os.path.isfile(REPORT)

    def test_valid_json(self):
        """validation-report.json must be valid JSON."""
        data = load_report()
        assert isinstance(data, dict)

    def test_passed_true(self):
        """The report must show passed=true."""
        data = load_report()
        assert data.get("passed") is True

    def test_policy_exceptions_covered(self):
        """At least 3 policy exceptions must be covered in the report."""
        data = load_report()
        covered = data.get("policy_exceptions_covered", [])
        assert len(covered) >= 3

    def test_shmmax_covered(self):
        """The /proc/sys/kernel/shmmax path must appear in covered exceptions."""
        data = load_report()
        paths = [e.get("path", "") for e in data.get("policy_exceptions_covered", [])]
        assert "/proc/sys/kernel/shmmax" in paths

    def test_gpu_covered(self):
        """The /dev/dri/renderD128 path must appear in covered exceptions."""
        data = load_report()
        paths = [e.get("path", "") for e in data.get("policy_exceptions_covered", [])]
        assert "/dev/dri/renderD128" in paths

    def test_gpu_covered_has_device_allow_directive(self):
        """/dev/dri/renderD128 covered entry must reference a DeviceAllow directive."""
        data = load_report()
        gpu_entry = next(
            (e for e in data.get("policy_exceptions_covered", []) if e.get("path") == "/dev/dri/renderD128"),
            None,
        )
        assert gpu_entry is not None, "/dev/dri/renderD128 not in policy_exceptions_covered"
        assert "DeviceAllow" in gpu_entry.get("directive", ""), (
            f"directive for /dev/dri/renderD128 must contain 'DeviceAllow', got {gpu_entry.get('directive')!r}"
        )

    def test_fd_count_valid(self):
        """The fd_count_valid field must be true."""
        data = load_report()
        assert data.get("fd_count_valid") is True

    def test_fd_count_actual(self):
        """fd_count_actual must equal 15 (numeric fds 0-14 parsed from under-load.lsof)."""
        data = load_report()
        assert data.get("fd_count_actual") == 15, (
            f"Expected fd_count_actual=15, got {data.get('fd_count_actual')!r}"
        )

    def test_tmpfiles_complete(self):
        """The tmpfiles_complete field must be true."""
        data = load_report()
        assert data.get("tmpfiles_complete") is True

    def test_limit_nofile_valid(self):
        """limit_nofile_valid must be true: LimitNOFILE > fd_count_observed."""
        data = load_report()
        assert data.get("limit_nofile_valid") is True

    def test_limit_nofile_found(self):
        """limit_nofile_found must equal 64 (the LimitNOFILE value parsed from finchrender.service)."""
        data = load_report()
        assert data.get("limit_nofile_found") == 64, (
            f"Expected limit_nofile_found=64, got {data.get('limit_nofile_found')!r}"
        )

    def test_start_limit_policy_valid(self):
        """start_limit_policy_valid must be true: StartLimitBurst=5 and StartLimitIntervalSec=10min present."""
        data = load_report()
        assert data.get("start_limit_policy_valid") is True

    def test_issues_empty(self):
        """issues array must be empty when passed=true."""
        data = load_report()
        if data.get("passed"):
            assert data.get("issues", []) == []


class TestMilestone3Negative:
    """Negative contract: validator must re-read files and detect broken inputs."""

    def test_missing_limit_nofile_detected(self):
        """Removing LimitNOFILE= from finchrender.service must cause limit_nofile_valid=false."""
        with open(SERVICE) as fh:
            original = fh.read()
        try:
            broken = "\n".join(ln for ln in original.splitlines() if "LimitNOFILE" not in ln)
            with open(SERVICE, "w") as fh:
                fh.write(broken)
            report = rerun_validate()
            assert report.get("limit_nofile_valid") is False, (
                "limit_nofile_valid must be false when LimitNOFILE= is absent"
            )
            assert report.get("passed") is False
        finally:
            with open(SERVICE, "w") as fh:
                fh.write(original)
            rerun_validate()

    def test_missing_start_limit_burst_detected(self):
        """Removing StartLimitBurst=5 from finchrender.service must cause start_limit_policy_valid=false."""
        with open(SERVICE) as fh:
            original = fh.read()
        try:
            broken = "\n".join(ln for ln in original.splitlines() if "StartLimitBurst" not in ln)
            with open(SERVICE, "w") as fh:
                fh.write(broken)
            report = rerun_validate()
            assert report.get("start_limit_policy_valid") is False, (
                "start_limit_policy_valid must be false when StartLimitBurst=5 is absent"
            )
            assert report.get("passed") is False
        finally:
            with open(SERVICE, "w") as fh:
                fh.write(original)
            rerun_validate()

    def test_missing_device_allow_detected(self):
        """Removing DeviceAllow from finchrender.service must cause passed=false with issues."""
        with open(SERVICE) as fh:
            original = fh.read()
        try:
            broken = "\n".join(ln for ln in original.splitlines() if "DeviceAllow" not in ln)
            with open(SERVICE, "w") as fh:
                fh.write(broken)
            report = rerun_validate()
            assert report.get("passed") is False, (
                "passed must be false when DeviceAllow for /dev/dri/renderD128 is removed"
            )
            assert len(report.get("issues", [])) > 0, "issues must be non-empty when DeviceAllow is missing"
        finally:
            with open(SERVICE, "w") as fh:
                fh.write(original)
            rerun_validate()
