import json
import subprocess
from pathlib import Path

FORGE = Path("/app/environment")
OUT = Path("/app/output")
SPEC = json.loads((FORGE / "specs/operator.json").read_text())
TAIL_FIELDS = (
    "pack_id",
    "spill_total",
    "scratch_peak",
    "edge_mode",
    "lane_width",
    "divisors",
)


def _clear_output_dir():
    if not OUT.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        return
    for child in OUT.iterdir():
        if child.is_dir():
            for nested in sorted(child.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink()
                elif nested.is_dir():
                    nested.rmdir()
            child.rmdir()
        else:
            child.unlink()


def invoke_forge_compile(clean=True):
    if clean:
        _clear_output_dir()
    subprocess.run(
        [
            "node",
            "/app/environment/cli/driver.mjs",
            "compile",
            "--spec",
            "/app/environment/specs/operator.json",
            "--out",
            "/app/output",
        ],
        check=True,
    )


def invoke_forge_compile_incremental():
    subprocess.run(
        [
            "node",
            "/app/environment/cli/driver.mjs",
            "compile",
            "--spec",
            "/app/environment/specs/operator.json",
            "--out",
            "/app/output",
        ],
        check=True,
    )


def invoke_forge_migration():
    subprocess.run(
        ["node", "/app/environment/cli/driver.mjs", "cache-reset"],
        check=True,
    )


def invoke_forge_status():
    result = subprocess.run(
        [
            "node",
            "/app/environment/cli/driver.mjs",
            "status",
            "--trace",
            "/app/output/pass.trace.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def read_forge_triplet():
    trace = json.loads((OUT / "pass.trace.json").read_text())
    metrics = json.loads((OUT / "metrics.json").read_text())
    kernel = (OUT / "kernel.mjs").read_text()
    return trace, metrics, kernel


def read_replay_log():
    return json.loads((OUT / ".cache" / "replay_log.json").read_text())


def read_journal_epoch():
    journal = json.loads((OUT / ".cache" / "compile_journal.json").read_text())
    return journal["epoch"]


def read_wal_segments():
    path = OUT / ".cache" / "wal_segment.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return payload.get("segments", [])


def write_wal_segments(segments):
    (OUT / ".cache").mkdir(parents=True, exist_ok=True)
    (OUT / ".cache" / "wal_segment.json").write_text(json.dumps({"segments": segments}))


def write_journal_epoch(epoch):
    (OUT / ".cache").mkdir(parents=True, exist_ok=True)
    (OUT / ".cache" / "compile_journal.json").write_text(json.dumps({"epoch": epoch}))


def forge_trace_tail(trace):
    last = trace["records"][-1]
    return {key: last[key] for key in TAIL_FIELDS}


def forge_digest_hex(trace, kernel_source):
    tail = forge_trace_tail(trace)
    script = f"""
import {{ canonJson }} from 'file:///app/environment/lib/canon_json.mjs';
import {{ sha256Hex }} from 'file:///app/environment/lib/hash_util.mjs';
const tail = {json.dumps(tail)};
const kernel = {json.dumps(kernel_source)};
process.stdout.write(sha256Hex(canonJson(tail) + kernel));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_grid(name):
    return json.loads((FORGE / "fixtures/grids" / name).read_text())


def divisors(n):
    return [d for d in range(1, n + 1) if n % d == 0]


def shared_divisors(grid, ghost):
    ext = [grid["nx"] + 2 * ghost, grid["ny"] + 2 * ghost, grid["nz"] + 2 * ghost]
    common = set(divisors(ext[0]))
    for e in ext[1:]:
        common &= set(divisors(e))
    return sorted(common)


def peel_rows(grid):
    raw = grid["boundary_fraction"] * max(grid["nx"], grid["ny"], grid["nz"])
    base = int(raw)
    return base if raw == base else base + 1


def expected_pack_spill(pack, grid, ghost):
    cells = pack["tile"][0] * pack["tile"][1] * pack["tile"][2]
    ext = shared_divisors(grid, ghost)
    lane = max(d for d in ext if d <= 8)
    base = cells // lane
    peel = peel_rows(grid)
    cutoff = pack["predication_cutoff"]
    if grid["boundary_fraction"] > cutoff:
        return base + peel * 3
    return base + peel


def run_kernel(grid):
    eps = SPEC["tolerance"]["epsilon"]
    script = f"""
import {{ apply }} from 'file://{OUT}/kernel.mjs';
import {{ laplacian7, seededVolume }} from 'file://{FORGE}/runtime/ref_exec.mjs';
const grid = {json.dumps(grid)};
const vol = seededVolume(grid.nx, grid.ny, grid.nz, 17);
const got = apply(vol, grid.nx, grid.ny, grid.nz);
const expect = laplacian7(vol, grid.nx, grid.ny, grid.nz);
const eps = {eps};
for (let i = 0; i < got.length; i += 1) {{
  const denom = Math.max(Math.abs(expect[i]), 1.0);
  if (Math.abs(got[i] - expect[i]) / denom > eps) {{
    console.error('parity mismatch at', i);
    process.exit(1);
  }}
}}
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)


def spills_indexed_by_pack(trace):
    return {row["pack_id"]: row["spill_total"] for row in trace["records"]}


def assert_replay_lockstep(metrics):
    replay = read_replay_log()
    journal_epoch = read_journal_epoch()
    assert metrics["compile_epoch"] == journal_epoch
    assert metrics["replay_generation"] == journal_epoch
    assert replay["generation"] == journal_epoch


def count_replay_entries_for_generation(gen):
    replay = read_replay_log()
    return sum(1 for entry in replay["entries"] if entry["generation"] == gen)


def find_non_pack_upstream_cache(cache_dir):
    for path in sorted(cache_dir.glob("*.json")):
        stem = path.name[:-5]
        if stem.startswith("pack:"):
            continue
        if stem.startswith("stage_two"):
            continue
        if stem.startswith("trace:") or stem.startswith("digest:"):
            continue
        if stem in {"compile_journal", "replay_log", "wal_segment"}:
            continue
        return path
    return None


def find_stage_two_cache_file(cache_dir):
    for path in sorted(cache_dir.glob("*.json")):
        if path.name.startswith("stage_two:"):
            return path
    return None


def latest_replay_entry(replay):
    entries = replay["entries"]
    assert entries
    return entries[len(entries) - 1]


class TestStencilCodegenOptimization:
    def test_kernel_numeric_parity_all_packs(self):
        """Generated kernel matches reference executor numerics on every pack grid."""
        invoke_forge_compile()
        for pack in SPEC["packs"]:
            grid = load_grid(pack["grid_fixture"])
            run_kernel(grid)

    def test_wal_tail_next_epoch_wins_over_stale_journal(self):
        """WAL tail next_epoch reconciles compile_epoch when the journal file lags."""
        invoke_forge_compile()
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        _, metrics_after_migration, _ = read_forge_triplet()
        expected = metrics_after_migration["compile_epoch"]
        write_wal_segments(
            [{"seq": 1, "prior_epoch": expected - 1, "next_epoch": expected}]
        )
        write_journal_epoch(expected - 1)
        invoke_forge_compile_incremental()
        _, metrics, _ = read_forge_triplet()
        assert metrics["compile_epoch"] == expected
        assert read_journal_epoch() == expected
        assert_replay_lockstep(metrics)

    def test_wal_segments_cleared_after_migration_compile(self):
        """Successful post-migration compile clears WAL segments."""
        invoke_forge_compile()
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        assert read_wal_segments() == []

    def test_replay_generation_lockstep_after_reset_cycle(self):
        """Replay generation, journal epoch, and metrics epoch stay aligned across migration."""
        invoke_forge_compile()
        _, metrics, _ = read_forge_triplet()
        assert_replay_lockstep(metrics)
        epoch_first = metrics["compile_epoch"]
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        _, metrics, _ = read_forge_triplet()
        assert_replay_lockstep(metrics)
        assert metrics["compile_epoch"] == epoch_first + 1
        invoke_forge_compile_incremental()
        invoke_forge_compile_incremental()
        _, metrics, _ = read_forge_triplet()
        assert_replay_lockstep(metrics)
        assert metrics["compile_epoch"] == epoch_first + 1

    def test_replay_entry_count_tracks_successful_compiles(self):
        """replay_entry_count equals replay-log rows for the active generation."""
        invoke_forge_compile()
        _, metrics, _ = read_forge_triplet()
        assert metrics["replay_entry_count"] == 1
        assert count_replay_entries_for_generation(metrics["compile_epoch"]) == 1
        invoke_forge_compile_incremental()
        invoke_forge_compile_incremental()
        _, metrics, _ = read_forge_triplet()
        assert metrics["replay_entry_count"] == 3
        assert count_replay_entries_for_generation(metrics["compile_epoch"]) == 3

    def test_delayed_gamma_peel_stable_after_four_incremental_hits(self):
        """Gamma duplicate-mode peel spill stays correct across repeated stage-two cache hits."""
        invoke_forge_compile()
        ghost = SPEC["ghost_width"]
        pack = next(p for p in SPEC["packs"] if p["id"] == "gamma")
        grid = load_grid(pack["grid_fixture"])
        expected = expected_pack_spill(pack, grid, ghost)
        for _ in range(4):
            invoke_forge_compile_incremental()
            trace, _, _ = read_forge_triplet()
            gamma = next(r for r in trace["records"] if r["pack_id"] == "gamma")
            assert gamma["edge_mode"] == "duplicate"
            assert gamma["spill_total"] == expected

    def test_digest_poison_with_trace_hash_mismatch_recomputes(self):
        """Corrupt digest and trace_hash cache rows are ignored on recompile."""
        invoke_forge_compile()
        trace1, metrics1, kernel1 = read_forge_triplet()
        expected = forge_digest_hex(trace1, kernel1)
        assert metrics1["digest_chain"] == expected
        cache_dir = OUT / ".cache"
        digest_files = list(cache_dir.glob("digest:*.json"))
        assert digest_files
        poisoned = json.loads(digest_files[0].read_text())
        poisoned["data"]["digest"] = "a" * 64
        poisoned["data"]["trace_hash"] = "b" * 16
        digest_files[0].write_text(json.dumps(poisoned))
        invoke_forge_compile_incremental()
        trace2, metrics2, kernel2 = read_forge_triplet()
        assert metrics2["digest_chain"] == forge_digest_hex(trace2, kernel2)
        assert metrics2["digest_chain"] == expected

    def test_upstream_tiling_cache_miss_forces_spill_recompute(self):
        """Removing an upstream tiling cache forces stage-two spill to match clean totals."""
        invoke_forge_compile()
        trace_clean, _, _ = read_forge_triplet()
        spills_clean = spills_indexed_by_pack(trace_clean)
        cache_dir = OUT / ".cache"
        upstream = find_non_pack_upstream_cache(cache_dir)
        assert upstream is not None
        upstream.unlink()
        invoke_forge_compile_incremental()
        trace_after, metrics, _ = read_forge_triplet()
        assert spills_indexed_by_pack(trace_after) == spills_clean
        rolled = sum(row["spill_total"] for row in trace_after["records"])
        assert metrics["spill_total"] == rolled

    def test_stage_two_cache_miss_recomputes_gamma_spill(self):
        """Evicting a stage-two cache row recomputes gamma spill without drift."""
        invoke_forge_compile()
        invoke_forge_compile_incremental()
        trace_first, _, _ = read_forge_triplet()
        gamma_before = next(r for r in trace_first["records"] if r["pack_id"] == "gamma")
        cache_dir = OUT / ".cache"
        stage_file = find_stage_two_cache_file(cache_dir)
        assert stage_file is not None
        stage_file.unlink()
        invoke_forge_compile_incremental()
        trace_after, metrics, _ = read_forge_triplet()
        gamma_after = next(r for r in trace_after["records"] if r["pack_id"] == "gamma")
        assert gamma_after["spill_total"] == gamma_before["spill_total"]
        pack = next(p for p in SPEC["packs"] if p["id"] == "gamma")
        grid = load_grid(pack["grid_fixture"])
        assert gamma_after["spill_total"] == expected_pack_spill(pack, grid, SPEC["ghost_width"])
        assert metrics["spill_total"] == sum(r["spill_total"] for r in trace_after["records"])

    def test_interleaved_reset_compile_artifact_convergence(self):
        """Long reset/compile alternation converges to the same artifacts as a clean build."""
        invoke_forge_compile()
        trace_clean, metrics_clean, kernel_clean = read_forge_triplet()
        expected_epoch = metrics_clean["compile_epoch"]
        for _ in range(3):
            invoke_forge_compile_incremental()
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        expected_epoch += 1
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        expected_epoch += 1
        trace_b, metrics_b, kernel_b = read_forge_triplet()
        assert trace_b["records"] == trace_clean["records"]
        assert metrics_b["digest_chain"] == metrics_clean["digest_chain"]
        assert metrics_b["spill_total"] == metrics_clean["spill_total"]
        assert kernel_b == kernel_clean
        assert metrics_b["compile_epoch"] == expected_epoch
        assert read_wal_segments() == []

    def test_metrics_rollup_spec_order_after_wal_recovery_workflow(self):
        """Metrics rollups follow live trace spec order after WAL recovery and cache hits."""
        invoke_forge_compile()
        for _ in range(3):
            invoke_forge_compile_incremental()
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        _, metrics_after_migration, _ = read_forge_triplet()
        expected = metrics_after_migration["compile_epoch"]
        write_wal_segments(
            [{"seq": 1, "prior_epoch": expected - 1, "next_epoch": expected}]
        )
        write_journal_epoch(expected - 1)
        invoke_forge_compile_incremental()
        trace, metrics, _ = read_forge_triplet()
        by_id = {row["pack_id"]: row["lane_width"] for row in trace["records"]}
        expected_lanes = [by_id[pack["id"]] for pack in SPEC["packs"]]
        assert metrics["lane_width_summary"] == expected_lanes
        rolled = sum(row["spill_total"] for row in trace["records"])
        assert metrics["spill_total"] == rolled
        assert [r["pack_id"] for r in trace["records"]] == [p["id"] for p in SPEC["packs"]]
        assert_replay_lockstep(metrics)

    def test_seven_pass_incremental_bundle_invariant(self):
        """Seven incremental passes keep spill, digest, and replay generation stable."""
        invoke_forge_compile()
        baseline_spills = None
        digests = []
        generations = []
        for _ in range(7):
            trace, metrics, _ = read_forge_triplet()
            spills = spills_indexed_by_pack(trace)
            if baseline_spills is None:
                baseline_spills = spills
            else:
                assert spills == baseline_spills
            digests.append(metrics["digest_chain"])
            generations.append(metrics["replay_generation"])
            assert_replay_lockstep(metrics)
            invoke_forge_compile_incremental()
        assert len(set(digests)) == 1
        assert len(set(generations)) == 1

    def test_status_register_after_migration_workflow(self):
        """Status register estimate tracks trace spill sum after migration and replay."""
        invoke_forge_compile()
        invoke_forge_compile_incremental()
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        invoke_forge_compile_incremental()
        trace, metrics, _ = read_forge_triplet()
        status = invoke_forge_status()
        expected = sum(row["spill_total"] for row in trace["records"])
        assert status["register_estimate"] == expected
        assert status["register_estimate"] == metrics["spill_total"]
        assert expected > 0

    def test_double_reset_advances_epoch_and_clears_replay_stale_entries(self):
        """Two migration cycles advance epoch by two and keep replay rows generation-scoped."""
        invoke_forge_compile()
        _, metrics_start, _ = read_forge_triplet()
        expected_epoch = metrics_start["compile_epoch"]
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        expected_epoch += 1
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        expected_epoch += 1
        _, metrics_end, _ = read_forge_triplet()
        assert metrics_end["compile_epoch"] == expected_epoch
        assert_replay_lockstep(metrics_end)
        replay = read_replay_log()
        assert all(entry["generation"] == metrics_end["compile_epoch"] for entry in replay["entries"])
        assert metrics_end["replay_entry_count"] == 1
        last_entry = latest_replay_entry(replay)
        assert last_entry["digest"] == metrics_end["digest_chain"]

    def test_scratch_peak_temporal_cap_after_replay_migration(self):
        """Temporal tiling scratch caps hold after replay migration and cache hits."""
        invoke_forge_compile()
        for _ in range(2):
            invoke_forge_compile_incremental()
        invoke_forge_migration()
        invoke_forge_compile_incremental()
        trace, metrics, _ = read_forge_triplet()
        peaks = [row["scratch_peak"] for row in trace["records"]]
        assert metrics["max_scratch_bytes"] == max(peaks)
        for record in trace["records"]:
            pack = next(p for p in SPEC["packs"] if p["id"] == record["pack_id"])
            if pack["temporal_tiling"]:
                assert record["scratch_peak"] <= pack["scratch_cap_bytes"]
