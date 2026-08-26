"""Tests for milestone 1: manifest parsing and MySQL catalog connectivity."""

import hashlib
import json
import subprocess
from pathlib import Path


MANIFEST_PATH = Path("/app/build/parsed_manifest.json")
SERVICES_YAML = Path("/app/priv/manifests/services.yaml")
TOOLCHAIN_TOML = Path("/app/priv/manifests/toolchain.toml")
PRIV_ROOT = Path("/app/priv")

PRIV_SHA256: dict[str, str] = {
    "/app/priv/manifests/services.yaml": (
        "fa3a083fffeeb9240fbf305258c9d40a85ab234ceda0723cb70cb79ed2de3eba"
    ),
    "/app/priv/manifests/toolchain.toml": (
        "a630e18c43242bc356ab5610f81966478bf04fcafe75eafb5cfdb94afe7f2304"
    ),
    "/app/priv/schemas/lock.schema.json": (
        "be6e00aa5ecc4e3d5eaa7e144b83db0518e826b193a0f3a5e9323728ba7e8a18"
    ),
    "/app/priv/sql/init.sql": (
        "55f461285f4fd46dd2af226bb17ec703bb013eb41c0b382b6ca1ce712993dd2f"
    ),
    "/app/priv/sql/seed.sql": (
        "381af74d4ef1ea8c7c918ea36a413bde9c39be78318dc4f66c645b091c3786a0"
    ),
}


def _start_mysql() -> None:
    subprocess.run(
        ["bash", "/app/scripts/start_mysql.sh"],
        check=True,
        capture_output=True,
        text=True,
    )


def _run_parse() -> None:
    result = subprocess.run(
        ["mix", "helix.parse"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mix helix.parse failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _mix_run(expr: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["mix", "run", "-e", expr],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestMilestone1:
    """Milestone 1: parse manifests and connect to MySQL."""

    @classmethod
    def setup_class(cls) -> None:
        _start_mysql()
        _run_parse()

    def test_parsed_manifest_exists(self) -> None:
        """mix helix.parse writes /app/build/parsed_manifest.json."""
        assert MANIFEST_PATH.exists(), f"{MANIFEST_PATH} does not exist"

    def test_parsed_manifest_top_level_keys(self) -> None:
        """JSON includes version, dependencies, toolchain, and platform."""
        payload = json.loads(MANIFEST_PATH.read_text())
        for key in ("version", "dependencies", "toolchain", "platform"):
            assert key in payload, f"missing top-level key {key!r}"

    def test_manifest_version(self) -> None:
        """version must be \"1\" from services.yaml."""
        payload = json.loads(MANIFEST_PATH.read_text())
        assert payload["version"] == "1"

    def test_dependency_names(self) -> None:
        """dependencies lists ecto_sql, myxql, and phoenix in alphabetical order."""
        payload = json.loads(MANIFEST_PATH.read_text())
        names = [dep["name"] for dep in payload["dependencies"]]
        assert names == ["ecto_sql", "myxql", "phoenix"]

    def test_dependency_pins(self) -> None:
        """dependencies carry manifest pins from services.yaml."""
        payload = json.loads(MANIFEST_PATH.read_text())
        pins = {dep["name"]: dep["pin"] for dep in payload["dependencies"]}
        assert pins == {
            "ecto_sql": "3.11.3",
            "myxql": "0.7.1",
            "phoenix": "1.7.14",
        }

    def test_toolchain_values(self) -> None:
        """toolchain contains elixir 1.16.3 and otp 26.2.5."""
        payload = json.loads(MANIFEST_PATH.read_text())
        assert payload["toolchain"]["elixir"] == "1.16.3"
        assert payload["toolchain"]["otp"] == "26.2.5"

    def test_platform_values(self) -> None:
        """platform contains os linux and arch amd64."""
        payload = json.loads(MANIFEST_PATH.read_text())
        assert payload["platform"]["os"] == "linux"
        assert payload["platform"]["arch"] == "amd64"

    def test_priv_files_unchanged(self) -> None:
        """priv/manifests, priv/sql, and priv/schemas were not modified."""
        for path in sorted(PRIV_ROOT.rglob("*")):
            if not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            key = str(path)
            assert key in PRIV_SHA256, f"unexpected file under priv: {key}"
            assert digest == PRIV_SHA256[key], f"{key} was modified"

    def test_catalog_connect(self) -> None:
        """connect/0 opens a catalog connection using config.exs settings."""
        _start_mysql()
        result = _mix_run(
            "{:ok, conn} = HelixPipeline.Catalog.Client.connect(); "
            "GenServer.stop(conn); IO.puts(\"connected\")"
        )
        assert result.returncode == 0, result.stderr
        assert "connected" in result.stdout

    def test_catalog_query_returns_string_keyed_rows(self) -> None:
        """query/3 returns {:ok, rows} with string column names."""
        _start_mysql()
        result = _mix_run(
            "alias HelixPipeline.Catalog.Client; "
            "{:ok, conn} = Client.connect(); "
            '{:ok, rows} = Client.query(conn, '
            '"SELECT package_name FROM dependency_approvals WHERE package_name = ?", '
            '["phoenix"]); '
            "GenServer.stop(conn); "
            "IO.puts(Jason.encode!(rows))"
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload == [{"package_name": "phoenix"}]

    def test_catalog_ping_returns_ok_when_mysql_up(self) -> None:
        """ping/0 returns :ok when the catalog accepts SELECT 1."""
        _start_mysql()
        result = _mix_run("IO.inspect(HelixPipeline.Catalog.Client.ping())")
        assert result.returncode == 0, result.stderr
        assert ":ok" in result.stdout

    def test_catalog_ping_fails_when_catalog_unreachable(self) -> None:
        """ping/0 returns {:error, _} when the catalog cannot be reached."""
        _start_mysql()
        result = _mix_run(
            "Application.ensure_all_started(:helix_pipeline); "
            "original = Application.get_env(:helix_pipeline, HelixPipeline.Catalog.Client); "
            "Application.put_env(:helix_pipeline, HelixPipeline.Catalog.Client, "
            "Keyword.put(original, :port, 59999)); "
            "IO.inspect(HelixPipeline.Catalog.Client.ping())"
        )
        assert result.returncode == 0, result.stderr
        assert "error" in result.stdout.lower()
        assert ":ok" not in result.stdout
