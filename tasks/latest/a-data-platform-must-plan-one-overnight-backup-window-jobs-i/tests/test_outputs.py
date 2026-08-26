import os
import sys
import json
import hashlib
from pathlib import Path

sys.path.insert(0, "/tests")
sys.path.insert(0, "/app/task_file/scripts")
from model import evaluate  # noqa: E402

INPUT = Path("/app/task_file/input_data")
OUTPUT = Path("/app/task_file/output_data")

INPUT_HASHES = {
    "jobs.jsonl": "086b261eb0bce42378a0525d1949c7ef0a6ff4f6d1d262f5e8b148aebbd573b7",
    "config.json": "e03061bc21ad5c5ea29b7e5d1ec9c699f1bc35526acdb594fd4acd3627997f4f",
}
MODEL_PY_SHA256 = "d8a605b61f690d28cbfde13704272c7a7b8438888f83fdac493b8a4c8e95e83c"

TOTAL_THRESHOLD = 0.90
LATENESS_FLOOR = 0.90
FRESHNESS_FLOOR = 0.88
REPLICATION_FLOOR = 0.84
NETWORK_FLOOR = 0.82
SCRATCH_FLOOR = 0.80
BALANCE_FLOOR = 0.78
MAX_WEIGHTED_LATENESS = 620
ALT_TOTAL_THRESHOLD = 0.86
ALT_LATENESS_FLOOR = 0.84
ALT_FRESHNESS_FLOOR = 0.80
ALT_REPLICATION_FLOOR = 0.72
ALT_MAX_WEIGHTED_LATENESS = 980
ALT_MAX_BALANCE_SPREAD = 520
ADV_TOTAL_THRESHOLD = 0.91
ADV_REPLICATION_FLOOR = 0.72
ADV_OPTIONAL_FLOOR = 0.62
ADV_MAX_WEIGHTED_LATENESS = 260
RATIO_TOTAL_THRESHOLD = 0.90
RATIO_OPTIONAL_FLOOR = 0.28
RATIO_MAX_NETWORK_PEAK = 430
RATIO_MAX_SCRATCH_GB = 760


def load_jobs():
    return [json.loads(line) for line in (INPUT / "jobs.jsonl").read_text().splitlines() if line.strip()]


def load_config():
    return json.loads((INPUT / "config.json").read_text())


def load_plan():
    return json.loads((OUTPUT / "plan.json").read_text())


def write_instance(jobs, config):
    (INPUT / "jobs.jsonl").write_text("".join(json.dumps(j, sort_keys=True) + "\n" for j in jobs))
    (INPUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")


def alternate_instance(seed=20260708, tight=False):
    import random
    rng = random.Random(seed)
    datasets = ["orders", "cards", "auth", "metrics", "warehouse", "crm", "ads"]
    workers = [{"id": f"aw{i}", "cpu": 7 + (i % 2)} for i in range(1, 6 if not tight else 5)]
    jobs = []
    deps = []
    conflicts = []
    for i, ds in enumerate(datasets):
        base = 20 + i * 21 + rng.randint(0, 12)
        mandatory = i < (5 if not tight else 6)
        priority = 5 if i < 3 else 4 if mandatory else 2
        snap = f"{ds}_s_{seed % 100}"
        val = f"{ds}_v_{seed % 100}"
        repl = f"{ds}_r_{seed % 100}"
        audit = f"{ds}_audit_{seed % 100}"
        jobs.append({"id": snap, "dataset": ds, "kind": "snapshot", "duration": rng.randint(38, 62), "earliest_start": base, "deadline": 250 + i * 23, "priority": priority, "cpu": 3, "network": rng.randint(95, 145), "scratch_gb": rng.randint(150, 240), "mandatory": mandatory, "produces_restore_point": True, "restore_value": 85 if mandatory else 42, "replication_value": 0, "optional_value": 18 if not mandatory else 0})
        jobs.append({"id": val, "dataset": ds, "kind": "validate", "duration": rng.randint(24, 40), "earliest_start": base + 20, "deadline": 330 + i * 24, "priority": priority, "cpu": 2, "network": rng.randint(35, 70), "scratch_gb": rng.randint(55, 95), "mandatory": mandatory, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 12 if not mandatory else 0})
        jobs.append({"id": repl, "dataset": ds, "kind": "replicate", "duration": rng.randint(42, 70), "earliest_start": base + 70, "deadline": 500 + i * 22, "priority": 3, "cpu": 2, "network": rng.randint(130, 190), "scratch_gb": rng.randint(80, 145), "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 72 if mandatory else 32, "optional_value": 62 if mandatory else 30})
        jobs.append({"id": audit, "dataset": ds, "kind": "compact", "duration": rng.randint(22, 44), "earliest_start": base + 50, "deadline": 610 + i * 16, "priority": 1, "cpu": 2, "network": rng.randint(25, 55), "scratch_gb": rng.randint(100, 180), "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 14})
        deps += [{"before": snap, "after": val}, {"before": val, "after": repl}, {"before": snap, "after": audit}]
        if i % 3 == 0:
            conflicts.append([audit, repl])
    deps.append({"before": jobs[1]["id"], "after": jobs[-2]["id"]})
    deps.append({"before": jobs[5]["id"], "after": jobs[10]["id"]})
    config = {
        "planning_start": 0,
        "planning_end": 760 if not tight else 820,
        "network_capacity": 700 if not tight else 640,
        "scratch_capacity_gb": 2200 if not tight else 1900,
        "workers": workers,
        "dependencies": deps,
        "conflicts": conflicts,
        "datasets": [{"dataset": ds, "target_time": 355 + i * 28, "weight": 1.8 if i < 4 else 1.1} for i, ds in enumerate(datasets)],
    }
    return jobs, config


def adversarial_instance():
    jobs = [
        {"id": "alpha_snap", "dataset": "alpha", "kind": "snapshot", "duration": 42, "earliest_start": 0, "deadline": 145, "priority": 5, "cpu": 3, "network": 105, "scratch_gb": 180, "mandatory": True, "produces_restore_point": True, "restore_value": 95, "replication_value": 0, "optional_value": 0},
        {"id": "alpha_val", "dataset": "alpha", "kind": "validate", "duration": 24, "earliest_start": 35, "deadline": 205, "priority": 5, "cpu": 2, "network": 45, "scratch_gb": 55, "mandatory": True, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 0},
        {"id": "alpha_repl", "dataset": "alpha", "kind": "replicate", "duration": 54, "earliest_start": 80, "deadline": 330, "priority": 3, "cpu": 2, "network": 165, "scratch_gb": 120, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 115, "optional_value": 95},
        {"id": "alpha_bulk_compact", "dataset": "alpha", "kind": "compact", "duration": 180, "earliest_start": 60, "deadline": 410, "priority": 1, "cpu": 4, "network": 210, "scratch_gb": 520, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 24},
        {"id": "beta_snap", "dataset": "beta", "kind": "snapshot", "duration": 48, "earliest_start": 0, "deadline": 160, "priority": 5, "cpu": 3, "network": 115, "scratch_gb": 200, "mandatory": True, "produces_restore_point": True, "restore_value": 90, "replication_value": 0, "optional_value": 0},
        {"id": "beta_val", "dataset": "beta", "kind": "validate", "duration": 26, "earliest_start": 45, "deadline": 225, "priority": 5, "cpu": 2, "network": 55, "scratch_gb": 60, "mandatory": True, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 0},
        {"id": "beta_repl", "dataset": "beta", "kind": "replicate", "duration": 58, "earliest_start": 95, "deadline": 355, "priority": 3, "cpu": 2, "network": 175, "scratch_gb": 130, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 120, "optional_value": 100},
        {"id": "beta_fast_but_local", "dataset": "beta", "kind": "compact", "duration": 32, "earliest_start": 90, "deadline": 260, "priority": 1, "cpu": 2, "network": 60, "scratch_gb": 75, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 70},
        {"id": "gamma_snap", "dataset": "gamma", "kind": "snapshot", "duration": 44, "earliest_start": 25, "deadline": 185, "priority": 4, "cpu": 3, "network": 100, "scratch_gb": 170, "mandatory": True, "produces_restore_point": True, "restore_value": 76, "replication_value": 0, "optional_value": 0},
        {"id": "gamma_val", "dataset": "gamma", "kind": "validate", "duration": 22, "earliest_start": 70, "deadline": 245, "priority": 4, "cpu": 2, "network": 45, "scratch_gb": 50, "mandatory": True, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 0},
        {"id": "gamma_repl", "dataset": "gamma", "kind": "replicate", "duration": 50, "earliest_start": 120, "deadline": 385, "priority": 2, "cpu": 2, "network": 145, "scratch_gb": 110, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 78, "optional_value": 66},
        {"id": "delta_optional_restore", "dataset": "delta", "kind": "snapshot", "duration": 40, "earliest_start": 150, "deadline": 430, "priority": 2, "cpu": 2, "network": 80, "scratch_gb": 140, "mandatory": False, "produces_restore_point": True, "restore_value": 55, "replication_value": 0, "optional_value": 48},
    ]
    config = {
        "planning_start": 0,
        "planning_end": 620,
        "network_capacity": 520,
        "scratch_capacity_gb": 980,
        "workers": [{"id": "dw1", "cpu": 6}, {"id": "dw2", "cpu": 6}, {"id": "dw3", "cpu": 5}],
        "dependencies": [
            {"before": "alpha_snap", "after": "alpha_val"},
            {"before": "alpha_val", "after": "alpha_repl"},
            {"before": "beta_snap", "after": "beta_val"},
            {"before": "beta_val", "after": "beta_repl"},
            {"before": "gamma_snap", "after": "gamma_val"},
            {"before": "gamma_val", "after": "gamma_repl"},
        ],
        "conflicts": [["alpha_repl", "alpha_bulk_compact"], ["beta_repl", "beta_fast_but_local"]],
        "datasets": [
            {"dataset": "alpha", "target_time": 175, "weight": 2.2},
            {"dataset": "beta", "target_time": 190, "weight": 2.1},
            {"dataset": "gamma", "target_time": 225, "weight": 1.7},
            {"dataset": "delta", "target_time": 420, "weight": 0.8},
        ],
    }
    return jobs, config


def ratio_trap_instance():
    jobs = [
        {"id": "core_a_snap", "dataset": "core-a", "kind": "snapshot", "duration": 34, "earliest_start": 0, "deadline": 115, "priority": 5, "cpu": 3, "network": 95, "scratch_gb": 160, "mandatory": True, "produces_restore_point": True, "restore_value": 88, "replication_value": 0, "optional_value": 0},
        {"id": "core_a_val", "dataset": "core-a", "kind": "validate", "duration": 20, "earliest_start": 25, "deadline": 170, "priority": 5, "cpu": 2, "network": 35, "scratch_gb": 45, "mandatory": True, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 0},
        {"id": "core_b_snap", "dataset": "core-b", "kind": "snapshot", "duration": 36, "earliest_start": 8, "deadline": 125, "priority": 5, "cpu": 3, "network": 100, "scratch_gb": 170, "mandatory": True, "produces_restore_point": True, "restore_value": 82, "replication_value": 0, "optional_value": 0},
        {"id": "core_b_val", "dataset": "core-b", "kind": "validate", "duration": 22, "earliest_start": 35, "deadline": 185, "priority": 5, "cpu": 2, "network": 40, "scratch_gb": 50, "mandatory": True, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 0},
        {"id": "core_c_snap", "dataset": "core-c", "kind": "snapshot", "duration": 38, "earliest_start": 16, "deadline": 150, "priority": 4, "cpu": 3, "network": 90, "scratch_gb": 150, "mandatory": True, "produces_restore_point": True, "restore_value": 74, "replication_value": 0, "optional_value": 0},
        {"id": "core_c_val", "dataset": "core-c", "kind": "validate", "duration": 20, "earliest_start": 55, "deadline": 215, "priority": 4, "cpu": 2, "network": 35, "scratch_gb": 45, "mandatory": True, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 0},
        {"id": "cheap_repl_a", "dataset": "core-a", "kind": "replicate", "duration": 34, "earliest_start": 75, "deadline": 275, "priority": 2, "cpu": 1, "network": 85, "scratch_gb": 65, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 60, "optional_value": 46},
        {"id": "cheap_repl_b", "dataset": "core-b", "kind": "replicate", "duration": 36, "earliest_start": 85, "deadline": 300, "priority": 2, "cpu": 1, "network": 90, "scratch_gb": 70, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 62, "optional_value": 48},
        {"id": "cheap_repl_c", "dataset": "core-c", "kind": "replicate", "duration": 38, "earliest_start": 100, "deadline": 330, "priority": 2, "cpu": 1, "network": 88, "scratch_gb": 68, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 58, "optional_value": 44},
        {"id": "fat_archive_a", "dataset": "core-a", "kind": "compact", "duration": 125, "earliest_start": 60, "deadline": 360, "priority": 1, "cpu": 4, "network": 230, "scratch_gb": 520, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 170},
        {"id": "fat_archive_b", "dataset": "core-b", "kind": "compact", "duration": 130, "earliest_start": 70, "deadline": 380, "priority": 1, "cpu": 4, "network": 235, "scratch_gb": 540, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 180},
        {"id": "tiny_restore_d", "dataset": "edge-d", "kind": "snapshot", "duration": 28, "earliest_start": 140, "deadline": 395, "priority": 1, "cpu": 1, "network": 45, "scratch_gb": 60, "mandatory": False, "produces_restore_point": True, "restore_value": 28, "replication_value": 0, "optional_value": 26},
    ]
    config = {
        "planning_start": 0,
        "planning_end": 520,
        "network_capacity": 430,
        "scratch_capacity_gb": 760,
        "workers": [{"id": "rw1", "cpu": 5}, {"id": "rw2", "cpu": 5}, {"id": "rw3", "cpu": 4}],
        "dependencies": [
            {"before": "core_a_snap", "after": "core_a_val"},
            {"before": "core_a_val", "after": "cheap_repl_a"},
            {"before": "core_b_snap", "after": "core_b_val"},
            {"before": "core_b_val", "after": "cheap_repl_b"},
            {"before": "core_c_snap", "after": "core_c_val"},
            {"before": "core_c_val", "after": "cheap_repl_c"},
        ],
        "conflicts": [["cheap_repl_a", "fat_archive_a"], ["cheap_repl_b", "fat_archive_b"]],
        "datasets": [
            {"dataset": "core-a", "target_time": 135, "weight": 2.4},
            {"dataset": "core-b", "target_time": 150, "weight": 2.2},
            {"dataset": "core-c", "target_time": 175, "weight": 1.8},
            {"dataset": "edge-d", "target_time": 390, "weight": 0.7},
        ],
    }
    return jobs, config


class TestInputIntegrity:
    def test_jobs_hash(self):
        assert hashlib.sha256((INPUT / "jobs.jsonl").read_bytes()).hexdigest() == INPUT_HASHES["jobs.jsonl"]

    def test_config_hash(self):
        assert hashlib.sha256((INPUT / "config.json").read_bytes()).hexdigest() == INPUT_HASHES["config.json"]


class TestModelIntegrity:
    def test_model_script_not_tampered(self):
        h = hashlib.sha256(Path("/app/task_file/scripts/model.py").read_bytes()).hexdigest()
        assert h == MODEL_PY_SHA256, "model.py has been modified"


class TestOutputSchema:
    def test_output_exists(self):
        assert (OUTPUT / "plan.json").exists()

    def test_plan_shape(self):
        plan = load_plan()
        assert isinstance(plan, dict)
        assert isinstance(plan.get("assignments"), list)
        for a in plan["assignments"]:
            assert isinstance(a.get("job"), str)
            assert isinstance(a.get("worker"), str)
            assert isinstance(a.get("start_time"), int) and not isinstance(a.get("start_time"), bool)

    def test_mandatory_jobs_assigned_once(self):
        jobs = load_jobs()
        ids = {j["id"] for j in jobs}
        mandatory = {j["id"] for j in jobs if j["mandatory"]}
        seen = [a["job"] for a in load_plan()["assignments"]]
        assert len(seen) == len(set(seen)), "duplicate job assignment"
        assert set(seen) <= ids, "unknown job id in assignments"
        assert mandatory <= set(seen), "not every mandatory job is assigned"

    def test_workers_known(self):
        workers = {w["id"] for w in load_config()["workers"]}
        for a in load_plan()["assignments"]:
            assert a["worker"] in workers, f"unknown worker {a['worker']}"


class TestScoreThreshold:
    def test_total_score(self):
        result = evaluate(str(INPUT), str(OUTPUT))
        assert "error" not in result, result.get("error")
        assert result["total_score"] >= TOTAL_THRESHOLD, f"score too low: {result}"

    def test_subscores_and_raw_limits(self):
        result = evaluate(str(INPUT), str(OUTPUT))
        assert "error" not in result, result.get("error")
        assert result["lateness_score"] >= LATENESS_FLOOR, result
        assert result["freshness_score"] >= FRESHNESS_FLOOR, result
        assert result["replication_score"] >= REPLICATION_FLOOR, result
        assert result["network_score"] >= NETWORK_FLOOR, result
        assert result["scratch_score"] >= SCRATCH_FLOOR, result
        assert result["balance_score"] >= BALANCE_FLOOR, result
        assert result["weighted_lateness"] <= MAX_WEIGHTED_LATENESS, result
        cfg = load_config()
        assert result["max_network_peak"] <= cfg["network_capacity"]
        assert result["max_scratch_gb"] <= cfg["scratch_capacity_gb"]


class TestRustImplementation:
    def test_cargo_toml_exists(self):
        assert Path("/app/task_file/backupplanner/Cargo.toml").exists(), "No backupplanner Cargo.toml found"

    def test_compiled_binary_exists(self):
        binary = Path("/app/task_file/backupplanner/target/release/backupplanner")
        assert binary.exists() and os.access(binary, os.X_OK), "No compiled backupplanner binary found"

    def test_binary_produces_output(self):
        import subprocess
        binary = Path("/app/task_file/backupplanner/target/release/backupplanner")
        fresh = OUTPUT / "plan.json"
        if fresh.exists():
            fresh.unlink()
        result = subprocess.run([str(binary)], cwd="/tmp", env={**os.environ, "HOME": "/root"}, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr[:300]
        assert fresh.exists(), "Binary did not write plan.json"
        r = evaluate(str(INPUT), str(OUTPUT))
        assert "error" not in r, r.get("error")
        assert r["total_score"] >= TOTAL_THRESHOLD, r

    def test_dynamic_input_not_hardcoded(self):
        import subprocess
        jobs_path = INPUT / "jobs.jsonl"
        backup = jobs_path.read_text()
        sentinel_snapshot = {"id": "sentinel_snapshot", "dataset": "sentinel", "kind": "snapshot", "duration": 24, "earliest_start": 80, "deadline": 250, "priority": 5, "cpu": 2, "network": 70, "scratch_gb": 110, "mandatory": True, "produces_restore_point": True, "restore_value": 140, "replication_value": 0, "optional_value": 0}
        sentinel_validate = {"id": "sentinel_validate", "dataset": "sentinel", "kind": "validate", "duration": 18, "earliest_start": 95, "deadline": 310, "priority": 5, "cpu": 2, "network": 35, "scratch_gb": 50, "mandatory": False, "produces_restore_point": False, "restore_value": 0, "replication_value": 0, "optional_value": 180}
        config_path = INPUT / "config.json"
        config_backup = config_path.read_text()
        cfg = json.loads(config_backup)
        cfg["dependencies"].append({"before": "sentinel_snapshot", "after": "sentinel_validate"})
        cfg["datasets"].append({"dataset": "sentinel", "target_time": 300, "weight": 2.5})
        binary = Path("/app/task_file/backupplanner/target/release/backupplanner")
        try:
            jobs_path.write_text(backup.rstrip("\n") + "\n" + json.dumps(sentinel_snapshot, sort_keys=True) + "\n" + json.dumps(sentinel_validate, sort_keys=True) + "\n")
            config_path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
            subprocess.run([str(binary)], check=True, timeout=120)
            assigned = {a["job"] for a in json.loads((OUTPUT / "plan.json").read_text())["assignments"]}
            assert "sentinel_snapshot" in assigned, "binary ignored mandatory sentinel job"
            assert "sentinel_validate" in assigned, "binary ignored high-value sentinel dependency"
        finally:
            jobs_path.write_text(backup)
            config_path.write_text(config_backup)
            try:
                subprocess.run([str(binary)], check=True, timeout=120)
            except Exception:
                pass

    def test_alternate_instance_quality(self):
        import subprocess
        jobs_backup = (INPUT / "jobs.jsonl").read_text()
        config_backup = (INPUT / "config.json").read_text()
        binary = Path("/app/task_file/backupplanner/target/release/backupplanner")
        try:
            for seed, tight in [(20260708, False), (20260709, True)]:
                jobs, config = alternate_instance(seed, tight)
                write_instance(jobs, config)
                fresh = OUTPUT / "plan.json"
                if fresh.exists():
                    fresh.unlink()
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=150)
                assert result.returncode == 0, result.stderr[:300]
                assert fresh.exists(), "Binary did not write plan.json for alternate instance"
                r = evaluate(str(INPUT), str(OUTPUT))
                assert "error" not in r, r.get("error")
                assert r["total_score"] >= ALT_TOTAL_THRESHOLD, r
                assert r["lateness_score"] >= ALT_LATENESS_FLOOR, r
                assert r["freshness_score"] >= ALT_FRESHNESS_FLOOR, r
                assert r["replication_score"] >= ALT_REPLICATION_FLOOR, r
                assert r["weighted_lateness"] <= ALT_MAX_WEIGHTED_LATENESS, r
                assert r["balance_spread"] <= ALT_MAX_BALANCE_SPREAD, r
        finally:
            (INPUT / "jobs.jsonl").write_text(jobs_backup)
            (INPUT / "config.json").write_text(config_backup)

    def test_adversarial_optional_dependency_tradeoffs(self):
        import subprocess
        jobs_backup = (INPUT / "jobs.jsonl").read_text()
        config_backup = (INPUT / "config.json").read_text()
        binary = Path("/app/task_file/backupplanner/target/release/backupplanner")
        try:
            jobs, config = adversarial_instance()
            write_instance(jobs, config)
            fresh = OUTPUT / "plan.json"
            if fresh.exists():
                fresh.unlink()
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=150)
            assert result.returncode == 0, result.stderr[:300]
            assert fresh.exists(), "Binary did not write plan.json for adversarial instance"
            assigned = {a["job"] for a in load_plan()["assignments"]}
            assert {"alpha_repl", "beta_repl", "gamma_repl"} <= assigned
            assert "alpha_bulk_compact" not in assigned
            assert "beta_fast_but_local" not in assigned
            r = evaluate(str(INPUT), str(OUTPUT))
            assert "error" not in r, r.get("error")
            assert r["total_score"] >= ADV_TOTAL_THRESHOLD, r
            assert r["replication_score"] >= ADV_REPLICATION_FLOOR, r
            assert r["optional_score"] >= ADV_OPTIONAL_FLOOR, r
            assert r["weighted_lateness"] <= ADV_MAX_WEIGHTED_LATENESS, r
            assert r["max_network_peak"] <= config["network_capacity"], r
            assert r["max_scratch_gb"] <= config["scratch_capacity_gb"], r
        finally:
            (INPUT / "jobs.jsonl").write_text(jobs_backup)
            (INPUT / "config.json").write_text(config_backup)

    def test_resource_ratio_optional_selection(self):
        import subprocess
        jobs_backup = (INPUT / "jobs.jsonl").read_text()
        config_backup = (INPUT / "config.json").read_text()
        binary = Path("/app/task_file/backupplanner/target/release/backupplanner")
        try:
            jobs, config = ratio_trap_instance()
            write_instance(jobs, config)
            fresh = OUTPUT / "plan.json"
            if fresh.exists():
                fresh.unlink()
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=150)
            assert result.returncode == 0, result.stderr[:300]
            assigned = {a["job"] for a in load_plan()["assignments"]}
            assert {"cheap_repl_a", "cheap_repl_b", "cheap_repl_c"} <= assigned
            assert {"fat_archive_a", "fat_archive_b"}.isdisjoint(assigned)
            r = evaluate(str(INPUT), str(OUTPUT))
            assert "error" not in r, r.get("error")
            assert r["total_score"] >= RATIO_TOTAL_THRESHOLD, r
            assert r["optional_score"] >= RATIO_OPTIONAL_FLOOR, r
            assert r["max_network_peak"] <= RATIO_MAX_NETWORK_PEAK, r
            assert r["max_scratch_gb"] <= RATIO_MAX_SCRATCH_GB, r
            assert r["weighted_lateness"] <= 180, r
        finally:
            (INPUT / "jobs.jsonl").write_text(jobs_backup)
            (INPUT / "config.json").write_text(config_backup)
