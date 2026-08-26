import os
import subprocess
from pathlib import Path

REPO = Path("/app/repo")


def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


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


class TestMilestone2:
    """Milestone 2 checks the repaired repo passes tests and keeps the intended behaviors."""

    def test_repo_tests_pass(self):
        res = _go_test("./...", "-count=1")
        assert res.returncode == 0, (
            f"go test ./... failed.\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        )

    def test_route_matching_is_exact(self):
        """Webhook routes must match exactly, not by prefix or case folding."""
        res = _go_test("./internal/routing", "-run", "^TestExactRouteMatch$", "-count=1")
        assert res.returncode == 0, (
            f"Exact route matching failed.\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        )
        content = (REPO / "internal/routing/match.go").read_text()
        assert "HasPrefix" not in content, (
            "Route matching still uses prefix checks; webhook routes must match exactly."
        )
        assert "EqualFold" not in content, (
            "Route matching still folds case; webhook routes must be case-sensitive."
        )

    def test_ledger_reload_behavior(self):
        res = _go_test("./internal/ledger", "-run", "^TestLedgerSurvivesReload$", "-count=1")
        assert res.returncode == 0, (
            f"Ledger reload behavior failed.\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        )

    def test_dispatch_order_behavior(self):
        res = _go_test("./internal/dispatch", "-run", "^TestDispatchPreservesSubmitOrder$", "-count=1")
        assert res.returncode == 0, (
            f"Dispatch order behavior failed.\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        )

    def test_deliver_idempotency_behavior(self):
        res = _go_test("./internal/deliver", "-run", "^TestDeliverIdempotent$", "-count=1")
        assert res.returncode == 0, (
            f"Delivery idempotency behavior failed.\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}"
        )

    def test_repository_on_main_branch(self):
        branch = _git("branch", "--show-current").stdout.strip()
        assert branch == "main", (
            f"Repository must be on main, currently on '{branch or 'detached HEAD'}'."
        )

    def test_git_status_is_clean(self):
        output = _git("status", "--porcelain").stdout.strip()
        assert output == "", f"Git working tree is not clean:\n{output}"
