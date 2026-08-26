import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import requests
import yaml

from reference_scorer import expected_mlflow_run, expected_report_from_done_queue
from queue_integrity import verify_queue_envelopes_match_trusted
from static_integrity import verify_static_inputs_unchanged

ROOT = Path("/app")
OUTPUT = ROOT / "output" / "drain_report.json"
TRACKING_URI = "http://127.0.0.1:5000"


@pytest.fixture(scope="session", autouse=True)
def mlflow_server():
    """Ensure MLflow tracking server is running for REST verification."""
    try:
        requests.get(f"{TRACKING_URI}/health", timeout=1)
        yield
        return
    except requests.RequestException:
        pass

    proc = subprocess.Popen(
        [
            "mlflow",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            "5000",
            "--backend-store-uri",
            "file:///app/mlflow_tracking",
            "--default-artifact-root",
            "file:///app/mlflow_artifacts",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            requests.get(f"{TRACKING_URI}/health", timeout=1)
            break
        except requests.RequestException:
            time.sleep(0.5)
    else:
        proc.kill()
        raise RuntimeError("MLflow server failed to start for tests")

    yield
    proc.terminate()


def get_experiment_id(name: str) -> str:
    resp = requests.get(
        f"{TRACKING_URI}/api/2.0/mlflow/experiments/get-by-name",
        params={"experiment_name": name},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()["experiment"]["experiment_id"]


def search_runs(experiment_id: str):
    resp = requests.post(
        f"{TRACKING_URI}/api/2.0/mlflow/runs/search",
        json={"experiment_ids": [experiment_id], "max_results": 50},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["runs"]


def test_drain_report_exists():
    """The worker must emit a drain report JSON file at the required path."""
    assert OUTPUT.exists(), f"Missing drain report at {OUTPUT}"


def test_verifier_config_paths_active():
    """Verifier must score using alternate config_paths env targets, not image defaults."""
    assert os.environ["READINESS_CONTRACT_PATH"].startswith("/logs/verifier/active/")
    assert os.environ["READINESS_RULES_PATH"].startswith("/logs/verifier/active/")
    assert os.environ["MLFLOW_MANIFEST_PATH"].startswith("/logs/verifier/active/")
    assert os.environ["MODEL_WEIGHTS_PATH"].startswith("/logs/verifier/active/")


def test_specs_and_model_unchanged():
    """Worker must not modify static deployment specs or model weights on disk."""
    verify_static_inputs_unchanged()


def test_queue_envelopes_match_verifier_copies():
    """Every done and seed envelope must exactly match verifier copies under /tests/data/pending."""
    verify_queue_envelopes_match_trusted()


def test_deferred_envelope_moved_to_done_queue():
    """Deferred envelopes must be renamed into done/ without scoring."""
    done_path = ROOT / "queue" / "done" / "job-006.json"
    assert done_path.exists(), "Deferred job-006 must land in the done queue"
    envelope = json.loads(done_path.read_text())
    assert envelope.get("defer") is True
    assert envelope["job_id"] == "job-006"


def test_drain_report_matches_reference_rebuild():
    """Drain report must match verifier reference rebuilt from done queue and configs."""
    actual = json.loads(OUTPUT.read_text())
    expected = expected_report_from_done_queue()
    assert actual["experiment"] == expected["experiment"]
    assert actual["jobs"] == expected["jobs"]
    assert actual["summary"] == expected["summary"]


def test_pending_queue_drained():
    """All pending envelopes must be moved to the done queue after draining."""
    pending = list((ROOT / "queue" / "pending").glob("*.json"))
    done = list((ROOT / "queue" / "done").glob("*.json"))
    assert pending == []
    assert len(done) == 15


def test_seed_directory_preserved():
    """Worker must not delete the verifier re-seed directory."""
    seed_dir = ROOT / "queue" / "pending" / ".seed"
    assert seed_dir.is_dir(), ".seed directory must survive the drain"
    assert len(list(seed_dir.glob("*.json"))) == 15


def test_mlflow_experiment_created():
    """Worker must log to the experiment named in the MLflow manifest."""
    expected = expected_report_from_done_queue()
    experiment_id = get_experiment_id(expected["experiment"])
    assert experiment_id


def test_mlflow_run_count_and_fields():
    """Each scored job must produce an MLflow run matching the reference scorer."""
    expected_report = expected_report_from_done_queue()
    experiment_id = get_experiment_id(expected_report["experiment"])
    runs = search_runs(experiment_id)

    scored_jobs = [j for j in expected_report["jobs"] if not j["deferred"]]
    assert len(runs) == len(scored_jobs)

    runs_by_job = {}
    for run in runs:
        params = {p["key"]: p["value"] for p in run["data"].get("params", [])}
        runs_by_job[params["job_id"]] = run

    for job in scored_jobs:
        expected = expected_mlflow_run(job["job_id"])
        assert expected is not None
        run = runs_by_job[job["job_id"]]
        params = {p["key"]: p["value"] for p in run["data"].get("params", [])}
        metrics = {m["key"]: m for m in run["data"].get("metrics", [])}
        tags = {t["key"]: t["value"] for t in run["data"].get("tags", [])}

        assert params == expected["params"]
        metric = metrics[expected["metric_key"]]
        assert metric["value"] == pytest.approx(expected["metric_value"], rel=0, abs=1e-6)
        assert metric["timestamp"] == expected["metric_timestamp_ms"]
        assert tags["verdict"] == expected["verdict"]
        assert tags["queue_priority"] == str(expected["priority"])

        artifact_path = (
            ROOT
            / "mlflow_artifacts"
            / experiment_id
            / run["info"]["run_id"]
            / "artifacts"
            / expected["artifact_name"]
        )
        assert artifact_path.exists(), f"Missing artifact for {job['job_id']}"
        artifact = json.loads(artifact_path.read_text())
        assert artifact == expected["artifact"]


def test_deferred_job_not_scored():
    """Deferred jobs must appear in the drain report without an MLflow run."""
    report = json.loads(OUTPUT.read_text())
    deferred = [j for j in report["jobs"] if j["deferred"]]
    assert len(deferred) == 1
    assert deferred[0]["job_id"] == "job-006"
    assert deferred[0]["verdict"] == "deferred"
    assert deferred[0]["readiness"] is None

    experiment_id = get_experiment_id(report["experiment"])
    runs = search_runs(experiment_id)
    job_ids = []
    for run in runs:
        params = {p["key"]: p["value"] for p in run["data"].get("params", [])}
        job_ids.append(params.get("job_id"))
    assert "job-006" not in job_ids


def test_job_001_multi_container_readiness():
    """job-001 readiness for a deployment with multiple containers."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-001")
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    sidecar = doc["spec"]["template"]["spec"]["containers"][0]
    assert sidecar["name"] == "metrics-sidecar"
    assert job["verdict"] == "ready"


def test_job_004_gpu_edge_readiness():
    """job-004 readiness under gpu_edge rules_ref."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-004")
    assert job["verdict"] == "not_ready"


def test_job_002_canary_profile_resolution():
    """job-002 profile_ref canary resolves to staging_lane."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-002")
    assert job["profile_ref"] == "canary"
    assert job["resolved_profile"] == "staging_lane"
    assert job["verdict"] == "ready"


def test_job_003_triton_stack_readiness():
    """job-003 readiness with rules_profile_stack on triton-edge."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-003")
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == "75%"
    assert job["readiness"] == pytest.approx(0.753757, rel=0, abs=1e-6)
    assert job["verdict"] == "not_ready"


def test_job_007_stack_precedence_readiness():
    """job-007 readiness when rules_profile_stack is set."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-007")
    assert job["readiness"] == pytest.approx(0.762693, rel=0, abs=1e-6)
    assert job["verdict"] == "not_ready"


def test_job_008_production_batch_readiness():
    """job-008 readiness on batch-cpu under production_lane."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-008")
    assert job["resolved_profile"] == "production_lane"
    assert job["readiness"] == pytest.approx(0.731304, rel=0, abs=1e-6)
    assert job["verdict"] == "not_ready"


def test_job_009_rolling_ceil_readiness():
    """job-009 readiness with ceil_of_replicas rolling adjustment."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-009")
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == "34%"
    assert job["readiness"] == pytest.approx(0.738126, rel=0, abs=1e-6)
    assert job["verdict"] == "not_ready"


def test_job_010_prefetch_deployment_readiness():
    """job-010 readiness for prefetch-v1 deployment."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-010")
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["template"]["spec"]["containers"][0]["name"] == "envoy-proxy"
    assert job["readiness"] == pytest.approx(0.774692, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_001_cpu_binding_readiness():
    """job-001 readiness score with cpu_request_norm binding resolution."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-001")
    assert job["readiness"] == pytest.approx(0.774692, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_002_mem_overlay_readiness():
    """job-002 readiness with overlay_rules_set mem_tight."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-002")
    assert job["readiness"] == pytest.approx(0.731304, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_015_legacy_gpu_stack_readiness():
    """job-015 applies edge_strict and roll_ceil via rules_profile_stack with first_wins."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-015")
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["template"]["spec"]["containers"][0].get("readinessProbe") is None
    assert job["resolved_profile"] == "staging_lane"
    assert job["readiness"] == pytest.approx(0.68298, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_011_qa_transitive_alias_readiness():
    """job-011 resolves qa through chained profile aliases and binding stack."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-011")
    assert job["profile_ref"] == "qa"
    assert job["resolved_profile"] == "staging_lane"
    assert job["readiness"] == pytest.approx(0.762693, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_012_analytics_transitive_alias_readiness():
    """job-012 resolves analytics through a four-hop profile alias chain."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-012")
    assert job["profile_ref"] == "analytics"
    assert job["resolved_profile"] == "staging_lane"
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["template"]["spec"]["containers"][0]["name"] == "metrics-sidecar"
    assert job["readiness"] == pytest.approx(0.736431, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_013_fleet_shadow_init_readiness():
    """job-013 resolves fleet through five profile hops and ignores initContainers."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-013")
    assert job["profile_ref"] == "fleet"
    assert job["resolved_profile"] == "staging_lane"
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["template"]["spec"]["initContainers"][0]["name"] == "model-server-bootstrap"
    assert "model.mlp.io/artifact-sha256" in doc["metadata"]["annotations"]
    assert (
        "model.mlp.io/artifact-sha256"
        not in doc["spec"]["template"]["metadata"].get("annotations", {})
    )
    assert job["readiness"] == pytest.approx(0.592138, rel=0, abs=1e-6)
    assert job["verdict"] == "ready"


def test_job_014_misnamed_container_readiness():
    """job-014 selects the first container when no name matches fallback_name_contains."""
    expected = expected_report_from_done_queue()
    job = next(item for item in expected["jobs"] if item["job_id"] == "job-014")
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    assert doc["spec"]["template"]["spec"]["containers"][0]["name"] == "log-collector"
    assert job["readiness"] == pytest.approx(0.63544, rel=0, abs=1e-6)
    assert job["verdict"] == "not_ready"
