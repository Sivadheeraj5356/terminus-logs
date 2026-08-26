"""Milestone 2 tests for transient-read fault injection and leak reproduction."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HEX_64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_OUTPUT_SHA256 = (
    "d82d787b068d9dddd1e9019fd1a86fb2"
    "0bc0426c8a0190b8a17025feb3ddd71c"
)
EXPECTED_REPORT = {
    "run_count": 64,
    "opened_descriptors": 64,
    "dropped_descriptors": 52,
    "leaked_descriptors": 24,
    "fault_count": 12,
}
COMPONENT_PATH = Path("/app/target/wasm32-wasip2/release/edge_worker.wasm")


def packed_output_sha256(fixtures: Path, rounds: int = 16, chunk_width: int = 3) -> str:
    """Compute the expected packed output hash for a host telemetry run."""
    output = bytearray()
    for _ in range(rounds):
        for path in sorted(fixtures.glob("*.bin")):
            data = path.read_bytes()
            for offset in range(0, len(data), chunk_width):
                output.extend(reversed(data[offset : offset + chunk_width]))
    return hashlib.sha256(output).hexdigest()


def audit_sha256(
    fixtures: Path,
    faulted_reads: set[int],
    fixture_faults: dict[str, set[int]] | None = None,
    rounds: int = 16,
    cleanup: bool = False,
) -> str:
    """Compute the expected descriptor audit hash for a configured host run."""
    fixture_faults = fixture_faults or {}
    fixture_reads: dict[str, int] = {}
    generations: dict[int, int] = {}
    open_descriptors: dict[int, int] = {}
    free: list[int] = []
    next_descriptor = 1
    lines: list[str] = []
    read_index = 0

    for _ in range(rounds):
        for path in sorted(fixtures.glob("*.bin")):
            read_index += 1
            fixture_name = path.name
            fixture_read = fixture_reads.get(fixture_name, 0) + 1
            fixture_reads[fixture_name] = fixture_read

            if free:
                descriptor = free.pop(0)
            else:
                descriptor = next_descriptor
                next_descriptor += 1
            generation = generations.get(descriptor, 0) + 1
            generations[descriptor] = generation
            open_descriptors[descriptor] = generation

            faulted = read_index in faulted_reads or fixture_read in fixture_faults.get(
                fixture_name, set()
            )
            status = "fault" if faulted else "ok"
            lines.append(
                f"{read_index}:{fixture_name}:{fixture_read}:"
                f"{descriptor}:{generation}:{status}\n"
            )

            if not faulted or cleanup:
                if open_descriptors.get(descriptor) == generation:
                    del open_descriptors[descriptor]
                    free.append(descriptor)
                    free.sort()

    return hashlib.sha256("".join(lines).encode()).hexdigest()


class TestMilestone2:
    """Verify the leaky high-throughput host run is reproduced."""

    def test_fault_harness_completes(self) -> None:
        """The fault runner should use the M1 wasip2 component and write a report."""
        assert COMPONENT_PATH.exists(), f"{COMPONENT_PATH} from milestone 1 is missing"
        result = subprocess.run(
            ["/app/tools/run-faults.sh"],
            cwd="/app",
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout

    def test_fault_runner_invokes_host_harness(self) -> None:
        """The fault runner should drive the host runner in leaky mode with the wasip2 artifact."""
        script = Path("/app/tools/run-faults.sh").read_text()
        assert "cargo run" in script
        assert "-p host-runner" in script
        assert str(COMPONENT_PATH) in script
        assert "--mode leaky" in script
        assert "--report /app/reports/fault-leak.json" in script
        assert "wasm32-wasip1" not in script

    def test_leak_report_schema_and_mode(self) -> None:
        """The leaky report should use the requested JSON fields and mode name."""
        report = json.loads(Path("/app/reports/fault-leak.json").read_text())
        assert report["mode"] == "leaky"
        for key in [
            "run_count",
            "opened_descriptors",
            "dropped_descriptors",
            "leaked_descriptors",
            "fault_count",
        ]:
            assert isinstance(report[key], int)
        assert HEX_64.fullmatch(report["output_sha256"])
        assert HEX_64.fullmatch(report["audit_sha256"])
        assert isinstance(report["observed_events"], list)

    def test_transient_faults_accumulate_descriptors(self) -> None:
        """Transient read lag should produce the deterministic leaky report."""
        report = json.loads(Path("/app/reports/fault-leak.json").read_text())
        for key, expected in EXPECTED_REPORT.items():
            assert report[key] == expected
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_fault_cadence_override_updates_leak_accounting(self) -> None:
        """FAULT_EVERY should change leak counts while preserving packed bytes."""
        report_path = Path("/tmp/fault-leak-every-7.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                str(COMPONENT_PATH),
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "leaky",
                "--report",
                str(report_path),
            ],
            cwd="/app",
            env={**os.environ, "FAULT_EVERY": "7"},
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        assert report["run_count"] == 64
        assert report["opened_descriptors"] == 64
        assert report["dropped_descriptors"] == 55
        assert report["leaked_descriptors"] == 18
        assert report["fault_count"] == 9
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256

    def test_every_read_faults_accumulates_all_leaks(self) -> None:
        """FAULT_EVERY=1 should leak every descriptor and queued error in leaky mode."""
        report_path = Path("/tmp/fault-leak-every-read.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                str(COMPONENT_PATH),
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "leaky",
                "--report",
                str(report_path),
            ],
            cwd="/app",
            env={**os.environ, "FAULT_EVERY": "1"},
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        assert report["run_count"] == 64
        assert report["opened_descriptors"] == 64
        assert report["dropped_descriptors"] == 0
        assert report["leaked_descriptors"] == 128
        assert report["fault_count"] == 64
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_fault_pattern_overrides_cadence(self) -> None:
        """FAULT_PATTERN should fault only listed reads, even with FAULT_EVERY set."""
        report_path = Path("/tmp/fault-leak-pattern.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                str(COMPONENT_PATH),
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "leaky",
                "--report",
                str(report_path),
            ],
            cwd="/app",
            env={
                **os.environ,
                "FAULT_EVERY": "1",
                "FAULT_PATTERN": "2,3,11-13,64,100,bad",
            },
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        assert report["run_count"] == 64
        assert report["opened_descriptors"] == 64
        assert report["dropped_descriptors"] == 58
        assert report["leaked_descriptors"] == 12
        assert report["fault_count"] == 6
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_fixture_scoped_fault_pattern_tracks_local_occurrences(self) -> None:
        """Fixture-scoped FAULT_PATTERN entries should combine with global indexes."""
        report_path = Path("/tmp/fault-leak-fixture-pattern.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                str(COMPONENT_PATH),
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "leaky",
                "--report",
                str(report_path),
            ],
            cwd="/app",
            env={
                **os.environ,
                "FAULT_EVERY": "1",
                "FAULT_PATTERN": "telemetry_03.bin@2-4,telemetry_01.bin@16,22,100,bad",
            },
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        assert report["run_count"] == 64
        assert report["opened_descriptors"] == 64
        assert report["dropped_descriptors"] == 59
        assert report["leaked_descriptors"] == 10
        assert report["fault_count"] == 5
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_round_and_chunk_overrides_change_counts_and_hash(self) -> None:
        """STREAM_ROUNDS and PACK_CHUNK should drive counters, faults, and hash."""
        report_path = Path("/tmp/fault-leak-rounds-chunk.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                str(COMPONENT_PATH),
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "leaky",
                "--report",
                str(report_path),
            ],
            cwd="/app",
            env={
                **os.environ,
                "STREAM_ROUNDS": "9",
                "PACK_CHUNK": "5",
                "FAULT_EVERY": "1",
                "FAULT_PATTERN": "telemetry_04.bin@2-3,7-8",
            },
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        assert report["run_count"] == 36
        assert report["opened_descriptors"] == 36
        assert report["dropped_descriptors"] == 33
        assert report["leaked_descriptors"] == 6
        assert report["fault_count"] == 3
        assert report["output_sha256"] == packed_output_sha256(
            Path("/app/fixtures"), rounds=9, chunk_width=5
        )
        assert report["audit_sha256"] == audit_sha256(
            Path("/app/fixtures"),
            faulted_reads={7, 8},
            fixture_faults={"telemetry_04.bin": {2, 3}},
            rounds=9,
        )
        assert report["output_sha256"] != EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_invalid_fault_cadence_uses_default_accounting(self) -> None:
        """Invalid FAULT_EVERY values should fall back to the default cadence."""
        report_path = Path("/tmp/fault-leak-invalid-cadence.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                str(COMPONENT_PATH),
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "leaky",
                "--report",
                str(report_path),
            ],
            cwd="/app",
            env={**os.environ, "FAULT_EVERY": "0"},
            text=True,
            capture_output=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        for key, expected in EXPECTED_REPORT.items():
            assert report[key] == expected
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256

    def test_host_runner_hashes_actual_packed_output(self) -> None:
        """The report hash should be data-derived, not a constant report value."""
        subprocess.run(
            ["/app/tools/build-component.sh"],
            cwd="/app",
            text=True,
            capture_output=True,
            timeout=120,
            check=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = Path(tmp) / "fixtures"
            shutil.copytree("/app/fixtures", fixtures)
            mutated = fixtures / "telemetry_03.bin"
            mutated.write_bytes(mutated.read_bytes() + b"\x9a\xbc\xde")
            report_path = Path(tmp) / "fault-leak-mutated.json"
            result = subprocess.run(
                [
                    "cargo",
                    "run",
                    "--quiet",
                    "-p",
                    "host-runner",
                    "--",
                    "--component",
                    str(COMPONENT_PATH),
                    "--fixtures",
                    str(fixtures),
                    "--mode",
                    "leaky",
                    "--report",
                    str(report_path),
                ],
                cwd="/app",
                text=True,
                capture_output=True,
                timeout=180,
            )
            assert result.returncode == 0, result.stderr + result.stdout
            report = json.loads(report_path.read_text())
            assert report["output_sha256"] == packed_output_sha256(fixtures)
            assert report["output_sha256"] != EXPECTED_OUTPUT_SHA256
