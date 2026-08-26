import os
import re
import subprocess
from pathlib import Path

REPO = Path("/app/repo")
PACKAGES = (
    "internal/routing",
    "internal/ledger",
    "internal/dispatch",
    "internal/deliver",
)


def _git(*args, **kwargs):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, **kwargs)


def _go_test(*test_args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GOCACHE"] = "/tmp/gocache"
    env["PATH"] = "/usr/local/go/bin:/usr/bin:/bin:" + env.get("PATH", "")
    return subprocess.run(
        ["go", "test", *test_args],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )


def _test_present(sha: str, test_name: str) -> bool:
    for pkg in PACKAGES:
        listing = _git("ls-tree", "--name-only", f"{sha}:{pkg}")
        if listing.returncode != 0:
            continue
        for fname in listing.stdout.splitlines():
            if not fname.endswith("_test.go"):
                continue
            content = _git("show", f"{sha}:{pkg}/{fname}")
            if content.returncode == 0 and f"func {test_name}" in content.stdout:
                return True
    return False


def _package_for_test(sha: str, test_name: str) -> str | None:
    for pkg in PACKAGES:
        listing = _git("ls-tree", "--name-only", f"{sha}:{pkg}")
        if listing.returncode != 0:
            continue
        for fname in listing.stdout.splitlines():
            if not fname.endswith("_test.go"):
                continue
            content = _git("show", f"{sha}:{pkg}/{fname}")
            if content.returncode == 0 and f"func {test_name}" in content.stdout:
                return f"./{pkg}"
    return None


class TestMilestone1:
    """Milestone 1 checks that every still-failing behavior is traced to its introducing commit."""
    # Capture the agent-left branch before helper methods perform any checkouts.
    _initial_branch = _git("branch", "--show-current").stdout.strip()

    def _failing_tests_at_head(self):
        _git("checkout", "-f", "main")
        res = _go_test("./...", "-count=1")
        failing = []
        for line in (res.stdout + res.stderr).splitlines():
            line = line.strip()
            if line.startswith("--- FAIL:"):
                parts = line.split()
                if len(parts) >= 3:
                    failing.append(parts[2])
        return sorted(set(failing))

    def _first_bad_commit(self, test_name: str) -> str:
        shas = _git("rev-list", "--reverse", "main").stdout.strip().split("\n")
        for sha in shas:
            sha = sha.strip()
            if not sha or not _test_present(sha, test_name):
                continue
            pkg = _package_for_test(sha, test_name)
            if not pkg:
                continue
            _git("checkout", sha, check=True)
            res = _go_test(pkg, "-run", f"^{test_name}$", "-count=1")
            if res.returncode != 0:
                return sha
        raise RuntimeError(f"Could not locate regression commit for {test_name}")

    def _expected_regression_shas(self):
        try:
            expected = set()
            for test_name in self._failing_tests_at_head():
                expected.add(self._first_bad_commit(test_name))
        finally:
            _git("checkout", "-f", "main")
            _git("switch", "-f", "main")
        return expected

    def _reported_shas(self):
        content = Path("/app/reports/regression_commits.txt").read_text()
        return {line.strip().lower() for line in content.splitlines() if line.strip()}

    def test_regression_file_exists(self):
        report_path = Path("/app/reports/regression_commits.txt")
        assert report_path.exists(), "Expected /app/reports/regression_commits.txt to exist."
        assert report_path.is_file(), "regression_commits.txt must be a file."

    def test_regression_commit_format(self):
        reported = self._reported_shas()
        assert reported, "regression_commits.txt is empty; expected one SHA per failing behavior."
        for sha in reported:
            assert re.match(r"^[0-9a-f]{40}$", sha), f"'{sha}' is not a valid 40-character hex SHA."

    def test_reports_dir_cleanliness(self):
        files = os.listdir("/app/reports")
        assert files == ["regression_commits.txt"], (
            f"/app/reports must contain only regression_commits.txt, found: {files}"
        )

    def test_all_regression_commits_identified(self):
        expected = {sha.lower() for sha in self._expected_regression_shas()}
        reported = self._reported_shas()
        assert reported == expected, (
            "Reported regression commits do not match the expected set.\n"
            f"Expected ({len(expected)}): {sorted(expected)}\n"
            f"Reported ({len(reported)}): {sorted(reported)}\n"
            f"Missing: {sorted(expected - reported)}\n"
            f"Extra: {sorted(reported - expected)}"
        )

    def test_regression_count_matches_failures(self):
        """Every failing test on main must have a corresponding regression SHA."""
        failing = self._failing_tests_at_head()
        reported = self._reported_shas()
        assert len(reported) == len(failing), (
            f"Expected {len(failing)} regression SHAs for failing tests {failing}, "
            f"got {len(reported)}."
        )

    def test_repository_on_main_branch(self):
        assert self._initial_branch == "main", (
            "Repository must be on main after milestone 1 before verifier helpers run; "
            f"captured '{self._initial_branch or 'detached HEAD'}'."
        )
