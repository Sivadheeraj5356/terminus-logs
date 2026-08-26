"""Milestone 3 tests for explicit cleanup of errored WASI stream resources."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


HEX_64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_OUTPUT_SHA256 = (
    "d82d787b068d9dddd1e9019fd1a86fb2"
    "0bc0426c8a0190b8a17025feb3ddd71c"
)


def packed_output_sha256(fixtures: Path, rounds: int, chunk_width: int) -> str:
    """Compute the expected packed output hash for a configured host run."""
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


class TestMilestone3:
    """Verify the fixed runner cleans up resources while preserving output."""

    def test_fixed_runner_completes_twice(self) -> None:
        """The cleanup mode should be idempotent across repeated high-throughput runs."""
        for _ in range(2):
            result = subprocess.run(
                ["/app/tools/run-fixed.sh"],
                cwd="/app",
                text=True,
                capture_output=True,
                timeout=180,
            )
            assert result.returncode == 0, result.stderr + result.stdout

    def test_fixed_report_schema_and_mode(self) -> None:
        """The fixed report should use the requested JSON fields and cleanup mode name."""
        report = json.loads(Path("/app/reports/fault-fixed.json").read_text())
        assert report["mode"] == "wasi-error-cleanup"
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

    def test_cleanup_drops_every_descriptor_after_faults(self) -> None:
        """The fixed run should still see transient faults but leave no descriptors leaked."""
        report = json.loads(Path("/app/reports/fault-fixed.json").read_text())
        assert report["fault_count"] >= 10
        assert report["observed_events"] == ["transient-read-lag"]
        assert report["opened_descriptors"] == report["dropped_descriptors"]
        assert report["leaked_descriptors"] == 0

    def test_cleanup_handles_every_read_faulting(self) -> None:
        """FAULT_EVERY=1 should still drop every descriptor and preserve output bytes."""
        report_path = Path("/tmp/fault-fixed-every-read.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                "/app/target/wasm32-wasip2/release/edge_worker.wasm",
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "wasi-error-cleanup",
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
        assert report["dropped_descriptors"] == 64
        assert report["leaked_descriptors"] == 0
        assert report["fault_count"] == 64
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_cleanup_handles_sparse_fault_pattern(self) -> None:
        """A sparse FAULT_PATTERN should clean only faulted reads and leave no leaks."""
        report_path = Path("/tmp/fault-fixed-pattern.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                "/app/target/wasm32-wasip2/release/edge_worker.wasm",
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "wasi-error-cleanup",
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
        assert report["dropped_descriptors"] == 64
        assert report["leaked_descriptors"] == 0
        assert report["fault_count"] == 6
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_cleanup_handles_fixture_scoped_fault_pattern(self) -> None:
        """Fixture-scoped FAULT_PATTERN entries should still clean every descriptor."""
        report_path = Path("/tmp/fault-fixed-fixture-pattern.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                "/app/target/wasm32-wasip2/release/edge_worker.wasm",
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "wasi-error-cleanup",
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
        assert report["dropped_descriptors"] == 64
        assert report["leaked_descriptors"] == 0
        assert report["fault_count"] == 5
        assert report["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_cleanup_respects_round_and_chunk_overrides(self) -> None:
        """Cleanup should use configured rounds and chunk width while leaving no leaks."""
        report_path = Path("/tmp/fault-fixed-rounds-chunk.json")
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--quiet",
                "-p",
                "host-runner",
                "--",
                "--component",
                "/app/target/wasm32-wasip2/release/edge_worker.wasm",
                "--fixtures",
                "/app/fixtures",
                "--mode",
                "wasi-error-cleanup",
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
        assert report["dropped_descriptors"] == 36
        assert report["leaked_descriptors"] == 0
        assert report["fault_count"] == 3
        assert report["output_sha256"] == packed_output_sha256(
            Path("/app/fixtures"), rounds=9, chunk_width=5
        )
        assert report["audit_sha256"] == audit_sha256(
            Path("/app/fixtures"),
            faulted_reads={7, 8},
            fixture_faults={"telemetry_04.bin": {2, 3}},
            rounds=9,
            cleanup=True,
        )
        assert report["output_sha256"] != EXPECTED_OUTPUT_SHA256
        assert report["observed_events"] == ["transient-read-lag"]

    def test_cleanup_preserves_packed_output_hash(self) -> None:
        """Cleanup must not change the packed telemetry output compared with the leaky repro."""
        subprocess.run(
            ["/app/tools/run-faults.sh"],
            cwd="/app",
            text=True,
            capture_output=True,
            timeout=180,
            check=True,
        )
        leaky = json.loads(Path("/app/reports/fault-leak.json").read_text())
        fixed = json.loads(Path("/app/reports/fault-fixed.json").read_text())
        assert fixed["output_sha256"] == EXPECTED_OUTPUT_SHA256
        assert fixed["output_sha256"] == leaky["output_sha256"]
