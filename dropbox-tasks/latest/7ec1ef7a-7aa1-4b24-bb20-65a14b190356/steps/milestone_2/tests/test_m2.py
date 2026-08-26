"""Tests for milestone 2: catalog join and validated lock emission."""

import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema
import tomli


PARSED_MANIFEST = Path("/app/build/parsed_manifest.json")
LOCK_PATH = Path("/app/build/helix.lock.toml")
SCHEMA_PATH = Path("/app/priv/schemas/lock.schema.json")
SERVICES_YAML = Path("/app/priv/manifests/services.yaml")


def _start_mysql() -> None:
    subprocess.run(
        ["bash", "/app/scripts/start_mysql.sh"],
        check=True,
        capture_output=True,
        text=True,
    )


def _run_lock() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["mix", "helix.lock"],
        cwd="/app",
        capture_output=True,
        text=True,
    )


def _mix_run(expr: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["mix", "run", "-e", expr],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _mariadb(sql: str) -> None:
    result = subprocess.run(
        ["mariadb", "-h127.0.0.1", "-uhelix", "-phelix", "helix_catalog", "-e", sql],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _canonical_manifest_hash(payload: dict) -> str:
    def sort_keys(value: object) -> object:
        if isinstance(value, dict):
            return {k: sort_keys(value[k]) for k in sorted(value)}
        if isinstance(value, list):
            return [sort_keys(item) for item in value]
        return value

    normalized = dict(payload)
    normalized["dependencies"] = sorted(
        payload["dependencies"], key=lambda dep: dep["name"]
    )
    canonical = json.dumps(sort_keys(normalized), separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _append_services_dependency(name: str, pin: str) -> str:
    original = SERVICES_YAML.read_text()
    addition = f'  - name: {name}\n    pin: "{pin}"\n'
    SERVICES_YAML.write_text(original.rstrip() + "\n" + addition)
    return original


def _restore_services_yaml(original: str) -> None:
    SERVICES_YAML.write_text(original)


class TestMilestone2:
    """Milestone 2: join catalog tables and emit validated lock file."""

    @classmethod
    def setup_class(cls) -> None:
        assert PARSED_MANIFEST.exists(), "milestone 1 artifact missing"
        _start_mysql()
        result = _run_lock()
        assert result.returncode == 0, (
            f"mix helix.lock failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_milestone_1_artifact_persists(self) -> None:
        """parsed_manifest.json from milestone 1 must still exist."""
        assert PARSED_MANIFEST.exists()

    def test_lock_file_exists(self) -> None:
        """mix helix.lock writes /app/build/helix.lock.toml."""
        assert LOCK_PATH.exists(), f"{LOCK_PATH} does not exist"

    def test_lock_passes_schema(self) -> None:
        """Lock file validates against priv/schemas/lock.schema.json."""
        schema = json.loads(SCHEMA_PATH.read_text())
        lock = tomli.loads(LOCK_PATH.read_text())
        jsonschema.validate(instance=lock, schema=schema)

    def test_myxql_uses_catalog_version(self) -> None:
        """myxql resolves to approved 0.7.0, not the 0.7.1 pin."""
        lock = tomli.loads(LOCK_PATH.read_text())
        myxql = lock["dependencies"]["myxql"]
        assert myxql["version"] == "0.7.0"
        assert myxql["source"] == "catalog"
        assert myxql["approval_status"] == "approved"

    def test_phoenix_catalog_source_and_constraint(self) -> None:
        """phoenix uses catalog source with a linux/amd64 constraint."""
        lock = tomli.loads(LOCK_PATH.read_text())
        phoenix = lock["dependencies"]["phoenix"]
        assert phoenix["source"] == "catalog"
        assert phoenix["approval_status"] == "approved"
        assert any(
            c["os"] == "linux" and c["arch"] == "amd64" for c in phoenix["constraints"]
        )

    def test_ecto_sql_catalog_source_and_constraint(self) -> None:
        """ecto_sql uses catalog source with a linux/amd64 constraint."""
        lock = tomli.loads(LOCK_PATH.read_text())
        ecto = lock["dependencies"]["ecto_sql"]
        assert ecto["source"] == "catalog"
        assert ecto["approval_status"] == "approved"
        assert any(
            c["os"] == "linux" and c["arch"] == "amd64" for c in ecto["constraints"]
        )

    def test_dependencies_sorted_in_output(self) -> None:
        """Dependencies appear in alphabetical order in the lock file text."""
        text = LOCK_PATH.read_text()
        phoenix_pos = text.index("[dependencies.phoenix]")
        ecto_pos = text.index("[dependencies.ecto_sql]")
        myxql_pos = text.index("[dependencies.myxql]")
        assert ecto_pos < myxql_pos < phoenix_pos

    def test_dependency_tables_use_bare_toml_keys(self) -> None:
        """Dependency table headers use bare identifiers, not quoted key segments."""
        text = LOCK_PATH.read_text()
        assert '[dependencies."' not in text
        assert '[[dependencies."' not in text

    def test_manifest_hash_matches_canonical(self) -> None:
        """metadata.manifest_hash matches SHA-256 of canonical manifest JSON."""
        manifest = json.loads(PARSED_MANIFEST.read_text())
        expected = _canonical_manifest_hash(manifest)
        lock = tomli.loads(LOCK_PATH.read_text())
        assert lock["metadata"]["manifest_hash"] == expected

    def test_lock_is_deterministic(self) -> None:
        """Re-running mix helix.lock produces byte-identical output."""
        first = LOCK_PATH.read_bytes()
        _start_mysql()
        result = _run_lock()
        assert result.returncode == 0, result.stderr
        second = LOCK_PATH.read_bytes()
        assert first == second

    def test_no_generated_at_field(self) -> None:
        """Lock omits metadata.generated_at for determinism."""
        lock = tomli.loads(LOCK_PATH.read_text())
        assert "generated_at" not in lock.get("metadata", {})

    def test_fetch_enriched_four_arity_direct(self) -> None:
        """fetch_enriched/4 must be implemented and return joined catalog rows."""
        _start_mysql()
        result = _mix_run(
            "alias HelixPipeline.Catalog.{Client, Queries}; "
            "{:ok, conn} = Client.connect(); "
            'data = Queries.fetch_enriched(conn, ["phoenix"], "linux", "amd64"); '
            "GenServer.stop(conn); "
            "IO.puts(Jason.encode!(data))"
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        phoenix = payload["phoenix"]
        assert phoenix["approval"]["package_name"] == "phoenix"
        assert phoenix["approval"]["approval_status"] == "approved"
        assert len(phoenix["constraints"]) == 1
        assert phoenix["constraints"][0]["os"] == "linux"

    def test_fetch_enriched_omits_packages_without_approval(self) -> None:
        """fetch_enriched/4 drops manifest deps with no approval row."""
        _start_mysql()
        result = _mix_run(
            "alias HelixPipeline.Catalog; "
            'keys = Catalog.fetch_enriched!(["phoenix", "ghost_pkg"], "linux", "amd64") '
            "|> Map.keys() |> Enum.sort(); "
            "IO.puts(Jason.encode!(keys))"
        )
        assert result.returncode == 0, result.stderr
        keys = json.loads(result.stdout.strip())
        assert keys == ["phoenix"]
        assert "ghost_pkg" not in keys

    def test_build_uses_pin_for_pending_runtime_approval(self) -> None:
        """Non-approved catalog rows keep the manifest pin with source \"pin\"."""
        _start_mysql()
        _mariadb(
            "INSERT INTO dependency_approvals (package_name, approved_version, "
            "approval_status) VALUES ('plug', '1.15.2', 'pending') "
            "ON DUPLICATE KEY UPDATE approved_version='1.15.2', "
            "approval_status='pending'"
        )
        try:
            result = _mix_run(
                "alias HelixPipeline.{Catalog, Lock.Builder}; "
                "manifest = %{" 
                'version: "1", '
                'dependencies: [%{"name" => "plug", "pin" => "1.15.0"}], '
                'toolchain: %{"elixir" => "1.16.3", "otp" => "26.2.5"}, '
                'platform: %{"os" => "linux", "arch" => "amd64"}'
                "}; "
                'catalog = Catalog.fetch_enriched!(["plug"], "linux", "amd64"); '
                "IO.puts(Builder.build(manifest, catalog))"
            )
            assert result.returncode == 0, result.stderr
            assert 'source = "pin"' in result.stdout
            assert 'version = "1.15.0"' in result.stdout
            assert 'approval_status = "pending"' in result.stdout
        finally:
            _mariadb("DELETE FROM dependency_approvals WHERE package_name = 'plug'")

    def test_lock_omits_manifest_dependency_without_approval(self) -> None:
        """Lock output excludes deps that have no catalog approval row."""
        _start_mysql()
        original = _append_services_dependency("ghost_pkg", "9.9.9")
        try:
            result = _run_lock()
            assert result.returncode == 0, result.stderr
            lock = tomli.loads(LOCK_PATH.read_text())
            assert "ghost_pkg" not in lock["dependencies"]
        finally:
            _restore_services_yaml(original)
            _run_lock()

    def test_lock_uses_pin_for_runtime_pending_dependency(self) -> None:
        """End-to-end lock keeps manifest pin when approval_status is pending."""
        _start_mysql()
        _mariadb(
            "INSERT INTO dependency_approvals (package_name, approved_version, "
            "approval_status) VALUES ('plug', '1.15.2', 'pending') "
            "ON DUPLICATE KEY UPDATE approved_version='1.15.2', "
            "approval_status='pending'"
        )
        original = _append_services_dependency("plug", "1.15.0")
        try:
            result = _run_lock()
            assert result.returncode == 0, result.stderr
            lock = tomli.loads(LOCK_PATH.read_text())
            plug = lock["dependencies"]["plug"]
            assert plug["version"] == "1.15.0"
            assert plug["source"] == "pin"
            assert plug["approval_status"] == "pending"
        finally:
            _restore_services_yaml(original)
            _mariadb("DELETE FROM dependency_approvals WHERE package_name = 'plug'")
            _run_lock()

    def test_build_uses_pin_for_rejected_runtime_approval(self) -> None:
        """Rejected catalog rows keep the manifest pin with source \"pin\"."""
        _start_mysql()
        _mariadb(
            "INSERT INTO dependency_approvals (package_name, approved_version, "
            "approval_status) VALUES ('plug', '1.15.2', 'rejected') "
            "ON DUPLICATE KEY UPDATE approved_version='1.15.2', "
            "approval_status='rejected'"
        )
        try:
            result = _mix_run(
                "alias HelixPipeline.{Catalog, Lock.Builder}; "
                "manifest = %{"
                'version: "1", '
                'dependencies: [%{"name" => "plug", "pin" => "1.15.0"}], '
                'toolchain: %{"elixir" => "1.16.3", "otp" => "26.2.5"}, '
                'platform: %{"os" => "linux", "arch" => "amd64"}'
                "}; "
                'catalog = Catalog.fetch_enriched!(["plug"], "linux", "amd64"); '
                "IO.puts(Builder.build(manifest, catalog))"
            )
            assert result.returncode == 0, result.stderr
            assert 'source = "pin"' in result.stdout
            assert 'version = "1.15.0"' in result.stdout
            assert 'approval_status = "rejected"' in result.stdout
        finally:
            _mariadb("DELETE FROM dependency_approvals WHERE package_name = 'plug'")

    def test_constraints_sorted_within_dependency(self) -> None:
        """Constraint rows are sorted os, arch, min_version, max_version."""
        result = _mix_run(
            "alias HelixPipeline.Lock.Builder; "
            "manifest = %{"
            'version: "1", '
            'dependencies: [%{"name" => "plug", "pin" => "1.15.0"}], '
            'toolchain: %{"elixir" => "1.16.3", "otp" => "26.2.5"}, '
            'platform: %{"os" => "linux", "arch" => "amd64"}'
            "}; "
            'catalog = %{"plug" => %{'
            '"approval" => %{'
            '"package_name" => "plug", '
            '"approved_version" => "1.15.2", '
            '"approval_status" => "approved"'
            "}, "
            '"constraints" => ['
            '%{"os" => "linux", "arch" => "arm64", "min_version" => "1.14.0", '
            '"max_version" => "1.14.99"}, '
            '%{"os" => "linux", "arch" => "amd64", "min_version" => "1.15.0", '
            '"max_version" => "1.15.99"}'
            "]}}; "
            "IO.puts(Builder.build(manifest, catalog))"
        )
        assert result.returncode == 0, result.stderr
        amd64_pos = result.stdout.index('arch = "amd64"')
        arm64_pos = result.stdout.index('arch = "arm64"')
        assert amd64_pos < arm64_pos
