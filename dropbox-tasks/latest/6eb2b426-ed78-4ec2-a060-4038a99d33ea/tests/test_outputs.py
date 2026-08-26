import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(
    os.environ.get("BEACON_DRIFT_PROJECT", "/workspace/beacon-drift-go-build-rescue")
)
CACHE_ROOT = Path("/tmp/beacon-drift-verifier-cache")


def offline_environment():
    env = os.environ.copy()
    env.update(
        {
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "GOTOOLCHAIN": "local",
            "GOCACHE": str(CACHE_ROOT / "build"),
            "GOMODCACHE": str(CACHE_ROOT / "modules"),
        }
    )
    return env


def run_cmd(args, *, cwd, check=True):
    return subprocess.run(
        args,
        cwd=cwd,
        env=offline_environment(),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def copy_checkout(destination):
    return Path(
        shutil.copytree(
            PROJECT_ROOT,
            destination,
            ignore=shutil.ignore_patterns(
                ".git",
                ".pytest_cache",
                "__pycache__",
                "bin",
                "dist",
                "coverage.out",
                "vendor",
            ),
        )
    )


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_config_layout(root):
    assert (root / "config" / "beacon_profiles.json").is_file()
    assert not (root / "internal" / "packets" / "config").exists()


def module_state(root):
    state = {}
    for name in ("go.mod", "go.sum"):
        path = root / name
        state[name] = file_digest(path) if path.exists() else None
    return state


def test_offline_standard_workflow_and_module_files_are_stable(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    before = module_state(checkout)

    for target in ("clean", "test", "build", "smoke"):
        run_cmd(["make", target], cwd=checkout)

    binary = checkout / "bin" / "beacon-drift"
    assert binary.is_file()
    assert os.access(binary, os.X_OK)
    assert module_state(checkout) == before
    assert_config_layout(checkout)


def test_test_target_covers_internal_packages(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    probe = checkout / "internal" / "packets" / "build_scope_probe_test.go"
    probe.write_text(
        'package packets\n\nimport "testing"\n\n'
        'func TestBuildScopeProbe(t *testing.T) { t.Fatal("scope-probe-ran") }\n',
        encoding="utf-8",
    )

    result = run_cmd(["make", "test"], cwd=checkout, check=False)

    assert result.returncode != 0
    assert "scope-probe-ran" in result.stdout + result.stderr
    assert_config_layout(checkout)


def test_release_binary_is_portable_without_checkout(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    run_cmd(["make", "build"], cwd=checkout)

    portable_dir = tmp_path / "portable"
    portable_dir.mkdir()
    binary = portable_dir / "beacon-drift"
    packet = portable_dir / "packet.json"
    output = portable_dir / "result.json"
    shutil.copy2(checkout / "bin" / "beacon-drift", binary)
    shutil.copy2(checkout / "fixtures" / "packet_valid.json", packet)
    shutil.rmtree(checkout)

    run_cmd(
        [
            str(binary),
            "--profile",
            "north-pier",
            "--input",
            str(packet),
            "--output",
            str(output),
        ],
        cwd=portable_dir,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["accepted"] is True
    assert payload["profile"] == "north-pier"


def test_release_binary_reports_policy_holds_without_smoke_script(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    run_cmd(["make", "build"], cwd=checkout)

    portable_dir = tmp_path / "portable"
    portable_dir.mkdir()
    binary = portable_dir / "beacon-drift"
    packet = portable_dir / "packet_invalid.json"
    output = portable_dir / "result.json"
    shutil.copy2(checkout / "bin" / "beacon-drift", binary)
    shutil.copy2(checkout / "fixtures" / "packet_invalid.json", packet)
    shutil.rmtree(checkout)

    result = run_cmd(
        [
            str(binary),
            "--profile",
            "north-pier",
            "--input",
            str(packet),
            "--output",
            str(output),
        ],
        cwd=portable_dir,
    )
    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == {
        "beacon_id": "NB-105",
        "profile": "north-pier",
        "accepted": False,
        "reasons": [
            "battery_below_policy",
            "drift_limit_exceeded",
            "zone_not_allowed",
        ],
        "severity": "hold",
    }


def test_release_binary_distinguishes_usage_and_profile_failures(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    run_cmd(["make", "build"], cwd=checkout)

    binary = checkout / "bin" / "beacon-drift"
    output = tmp_path / "result.json"
    usage = run_cmd([str(binary)], cwd=tmp_path, check=False)
    assert usage.returncode == 2
    assert "usage: beacon-drift" in usage.stderr

    unknown_profile = run_cmd(
        [
            str(binary),
            "--profile",
            "west-jetty",
            "--input",
            str(checkout / "fixtures" / "packet_valid.json"),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        check=False,
    )
    assert unknown_profile.returncode != 0
    assert "unknown profile" in unknown_profile.stderr
    assert not output.exists()


def test_release_binary_rejects_malformed_packet_without_result_file(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    run_cmd(["make", "build"], cwd=checkout)

    malformed = tmp_path / "malformed.json"
    output = tmp_path / "result.json"
    malformed.write_text('{"beacon_id": "NB-200", "sequence": ', encoding="utf-8")
    result = run_cmd(
        [
            str(checkout / "bin" / "beacon-drift"),
            "--profile",
            "north-pier",
            "--input",
            str(malformed),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode != 0
    assert not output.exists()


def test_equivalent_checkouts_produce_identical_path_clean_binary(tmp_path):
    first = copy_checkout(tmp_path / "first-location" / "checkout")
    second = copy_checkout(tmp_path / "different-location" / "checkout")

    run_cmd(["make", "build"], cwd=first)
    run_cmd(["make", "build"], cwd=second)

    first_binary = first / "bin" / "beacon-drift"
    second_binary = second / "bin" / "beacon-drift"
    assert file_digest(first_binary) == file_digest(second_binary)
    binary_bytes = first_binary.read_bytes()
    assert str(first).encode() not in binary_bytes
    assert str(second).encode() not in binary_bytes


def test_module_graph_is_offline_and_has_no_unused_external_dependency(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    result = run_cmd(["go", "list", "-m", "all"], cwd=checkout)
    modules = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    assert modules == ["example.com/coastal/beacon-drift"]
    assert not (checkout / "vendor").exists()


def test_clean_removes_supported_build_outputs(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    run_cmd(["make", "build"], cwd=checkout)
    assert (checkout / "bin" / "beacon-drift").exists()

    run_cmd(["make", "clean"], cwd=checkout)

    assert not (checkout / "bin").exists()
    assert not (checkout / "dist").exists()
    assert not (checkout / "coverage.out").exists()
    assert_config_layout(checkout)


def test_repository_remains_free_of_forbidden_generated_trees(tmp_path):
    checkout = copy_checkout(tmp_path / "checkout")
    run_cmd(["make", "test"], cwd=checkout)
    run_cmd(["make", "build"], cwd=checkout)

    forbidden_names = {
        "vendor",
        "__pycache__",
        ".pytest_cache",
        ".DS_Store",
        "coverage.out",
    }
    found = [path for path in checkout.rglob("*") if path.name in forbidden_names]
    assert found == []
