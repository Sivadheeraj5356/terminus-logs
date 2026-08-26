"""Independent promotion decision recomputation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from reference_db import load_candidate
from reference_manifest import digest_registered
from reference_policy import eval_is_fresh, latency_ceiling_ms

UPSTREAM_CONFIG = Path("/app/config/upstream.toml")
DEFAULT_COMPOSE = Path("/app/compose/inference.yml")
MIN_HOLDOUT_SAMPLES = 500


def _round3(value: float) -> float:
  return round(value, 3)


def _normalize_digest(value: str) -> str:
  prefix, _, body = value.partition(":")
  return f"{prefix.lower()}:{body.lower()}"


def _parse_upstream_mirror() -> Path:
  text = UPSTREAM_CONFIG.read_text()
  for line in text.splitlines():
    stripped = line.strip()
    if stripped.startswith("mirror_path"):
      return Path(stripped.split("=", 1)[1].strip().strip('"'))
  raise ValueError("mirror_path not found in upstream config")


def _tag_exists(mirror_path: Path, tag: str) -> bool:
  result = subprocess.run(
    ["git", "-C", str(mirror_path), "tag", "-l"],
    capture_output=True,
    text=True,
    check=True,
  )
  tags = {line.strip() for line in result.stdout.splitlines() if line.strip()}
  return tag in tags


def _load_canary_baseline(fixture_path: Path) -> dict:
  payload = json.loads(fixture_path.read_text())
  for run in payload.get("runs", []):
    if run.get("profile") == "canary":
      return run["baseline"]
  raise ValueError(f"no canary profile in {fixture_path}")


def _fixture_batch_id(fixture_path: Path) -> str:
  payload = json.loads(fixture_path.read_text())
  batch_id = payload.get("batch_id")
  if not isinstance(batch_id, str):
    raise ValueError(f"batch_id missing in {fixture_path}")
  return batch_id


def _parse_compose_labels(compose_path: Path) -> dict:
  payload = yaml.safe_load(compose_path.read_text())
  service = payload["services"]["inference"]
  labels = service.get("labels", {})
  return {
    "model_id": labels["atlas.model_id"],
    "sklearn_pin": labels["atlas.sklearn_pin"],
    "artifact_digest": labels["atlas.artifact_digest"],
  }


def expected_decision(
  candidate_id: str,
  db_path: Path | None = None,
  compose_path: Path | None = None,
  mirror_path: Path | None = None,
) -> dict:
  """Recompute the promotion decision from source artifacts."""
  db_path = db_path or Path("/app/data/eval.db")
  compose_path = compose_path or DEFAULT_COMPOSE
  mirror_path = mirror_path or _parse_upstream_mirror()

  candidate = load_candidate(db_path, candidate_id)
  if candidate is None:
    raise ValueError(f"unknown candidate: {candidate_id}")

  fixture_path = Path(candidate["canary_fixture"])
  baseline = _load_canary_baseline(fixture_path)
  fixture_batch = _fixture_batch_id(fixture_path)
  labels = _parse_compose_labels(compose_path)
  ceiling = latency_ceiling_ms(candidate["batch_id"])

  tag_present = _tag_exists(mirror_path, candidate["sklearn_pin"])
  canary_ok = fixture_batch == candidate["batch_id"]
  eval_fresh = eval_is_fresh(candidate["eval_completed_at"])
  metrics_ok = (
    _round3(candidate["accuracy"]) >= _round3(baseline["accuracy"])
    and _round3(candidate["macro_f1"]) >= _round3(baseline["macro_f1"])
  )
  latency_ok = candidate["latency_p99_ms"] <= ceiling
  compose_ok = (
    labels["model_id"] == candidate["model_id"]
    and labels["sklearn_pin"] == candidate["sklearn_pin"]
    and _normalize_digest(labels["artifact_digest"])
    == _normalize_digest(candidate["artifact_digest"])
  )
  holdout_ok = candidate["holdout_samples"] >= MIN_HOLDOUT_SAMPLES
  manifest_ok = digest_registered(
    candidate["model_id"],
    candidate["sklearn_pin"],
    candidate["artifact_digest"],
  )

  reasons: list[str] = []
  if not tag_present:
    reasons.append("upstream_tag_missing")
  if not metrics_ok:
    reasons.append("metric_regression")
  if not latency_ok:
    reasons.append("latency_breach")
  if not compose_ok:
    reasons.append("compose_metadata_mismatch")
  if not canary_ok:
    reasons.append("canary_batch_mismatch")
  if not eval_fresh:
    reasons.append("eval_stale")
  if not holdout_ok:
    reasons.append("holdout_sample_insufficient")
  if not manifest_ok:
    reasons.append("artifact_manifest_mismatch")

  approved = len(reasons) == 0
  return {
    "candidate_id": candidate_id,
    "approved": approved,
    "status": "approved" if approved else "rejected",
    "reasons": sorted(reasons),
    "checks": {
      "canary_ok": canary_ok,
      "compose_ok": compose_ok,
      "eval_fresh": eval_fresh,
      "holdout_ok": holdout_ok,
      "latency_ok": latency_ok,
      "manifest_ok": manifest_ok,
      "metrics_ok": metrics_ok,
      "upstream_tag_present": tag_present,
    },
  }
