"""Verifier tests for AtlasBatch Lua compose model promotion CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from reference_decision import expected_decision
from reference_policy import latency_ceiling_ms

CLI = ["lua5.1", "/app/bin/atlas-promote", "run"]
OUT = Path("/app/output/promotion-decision.json")
DECISION_SCHEMA = Path("/app/docs/promotion-decision.schema.json")
DEFAULT_COMPOSE = Path("/app/compose/inference.yml")
HAPPY_CANDIDATE = "CAND-2026-042"


def _run(
    candidate_id: str,
    compose_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    compose_path = compose_path or DEFAULT_COMPOSE
    return subprocess.run(
        CLI + ["--candidate", candidate_id, "--compose", str(compose_path)],
        capture_output=True,
        text=True,
    )


def _clear_output() -> None:
    if OUT.parent.exists():
        shutil.rmtree(OUT.parent)
    OUT.parent.mkdir(parents=True, exist_ok=True)


def _compose_with_label_change(field: str, new_value: str) -> Path:
    """Copy default compose with a single label field changed."""
    tmp = Path(tempfile.mkdtemp(prefix="compose-"))
    compose_copy = tmp / "inference.yml"
    text = DEFAULT_COMPOSE.read_text()
    if field == "model_id":
        text = text.replace('atlas.model_id: "rf-spam-v3"', f'atlas.model_id: "{new_value}"')
    elif field == "sklearn_pin":
        text = text.replace('atlas.sklearn_pin: "1.4.2"', f'atlas.sklearn_pin: "{new_value}"')
    elif field == "artifact_digest":
        text = text.replace(
            "sha256:a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcd",
            new_value,
        )
    else:
        raise ValueError(f"unsupported compose label field: {field}")
    compose_copy.write_text(text)
    return compose_copy


class TestHappyPath:
    """Approval path for a fully qualified candidate."""

    def setup_method(self) -> None:
        """Clear output artifacts before each test."""
        _clear_output()

    def test_run_exits_zero(self) -> None:
        """Pipeline must exit 0 when every gate passes."""
        res = _run(HAPPY_CANDIDATE)
        assert res.returncode == 0, res.stderr

    def test_happy_path_approves(self) -> None:
        """Default candidate must be approved with an empty reasons list."""
        _run(HAPPY_CANDIDATE)
        payload = json.loads(OUT.read_text())
        assert payload["approved"] is True
        assert payload["status"] == "approved"
        assert payload["reasons"] == []

    def test_decision_matches_reference(self) -> None:
        """Decision JSON must match the independent reference recomputation."""
        _run(HAPPY_CANDIDATE)
        payload = json.loads(OUT.read_text())
        expected = expected_decision(HAPPY_CANDIDATE)
        assert payload == expected


class TestRejections:
    """Rejection paths for individual gate failures."""

    def setup_method(self) -> None:
        """Clear output artifacts before each test."""
        _clear_output()

    def test_missing_upstream_tag_rejects(self) -> None:
        """Candidate with unknown sklearn pin must be rejected."""
        res = _run("CAND-2026-088")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload["approved"] is False
        assert "upstream_tag_missing" in payload["reasons"]

    def test_metric_regression_rejects(self) -> None:
        """Candidate below canary macro_f1 baseline must be rejected."""
        res = _run("CAND-2026-017")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload["approved"] is False
        assert "metric_regression" in payload["reasons"]

    def test_macro_f1_only_regression_rejects(self) -> None:
        """macro_f1 regression must reject even when accuracy meets baseline."""
        res = _run("CAND-2026-071")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-071")

    def test_accuracy_only_regression_rejects(self) -> None:
        """accuracy regression must reject even when macro_f1 meets baseline."""
        res = _run("CAND-2026-072")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-072")

    def test_shadow_profile_baseline_ignored(self) -> None:
        """Metrics above shadow but below canary baseline must still reject."""
        res = _run("CAND-2026-073")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-073")

    def test_multiple_gate_failures_sorted(self) -> None:
        """Every failed gate must appear in reasons, sorted alphabetically."""
        res = _run("CAND-2026-091")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-091")

    def test_latency_breach_rejects(self) -> None:
        """Candidate above default latency ceiling without waiver must be rejected."""
        res = _run("CAND-2026-099")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-099")

    def test_compose_artifact_digest_mismatch_rejects(self) -> None:
        """Altered compose digest must trigger compose_metadata_mismatch."""
        compose_copy = _compose_with_label_change(
            "artifact_digest",
            "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdead",
        )
        res = _run(HAPPY_CANDIDATE, compose_path=compose_copy)
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload["approved"] is False
        assert "compose_metadata_mismatch" in payload["reasons"]

    def test_compose_model_id_mismatch_rejects(self) -> None:
        """Compose model_id label must match the candidate row."""
        compose_copy = _compose_with_label_change("model_id", "rf-spam-v9")
        res = _run(HAPPY_CANDIDATE, compose_path=compose_copy)
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload["approved"] is False
        assert payload["reasons"] == ["compose_metadata_mismatch"]

    def test_compose_sklearn_pin_mismatch_rejects(self) -> None:
        """Compose sklearn_pin label must match the candidate row."""
        compose_copy = _compose_with_label_change("sklearn_pin", "1.4.3")
        res = _run(HAPPY_CANDIDATE, compose_path=compose_copy)
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision(HAPPY_CANDIDATE, compose_path=compose_copy)

    def test_metric_rounding_before_compare_approves(self) -> None:
        """Rounded macro_f1 tie must approve when raw values differ below 3dp."""
        res = _run("CAND-2026-055")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-055")

    def test_three_decimal_rounding_rejects(self) -> None:
        """macro_f1 below baseline after 3dp rounding must reject."""
        res = _run("CAND-2026-056")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-056")

    def test_latency_at_exact_ceiling_approves(self) -> None:
        """Latency equal to the default ceiling must not breach."""
        res = _run("CAND-2026-044")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-044")

    def test_eval_day_before_window_rejects(self) -> None:
        """Evaluation one day before the window start must be stale."""
        res = _run("CAND-2026-062")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-062")

    def test_canary_batch_mismatch_rejects(self) -> None:
        """Fixture batch_id must match the candidate batch_id column."""
        res = _run("CAND-2026-074")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-074")

    def test_eval_stale_rejects(self) -> None:
        """Evaluation completed before the active window must be rejected."""
        res = _run("CAND-2026-060")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-060")

    def test_eval_window_boundary_accepts(self) -> None:
        """Evaluation on the earliest acceptable date must pass the freshness gate."""
        res = _run("CAND-2026-061")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-061")

    def test_compose_ignores_shadow_service(self) -> None:
        """Default compose with a shadow service must still approve the happy path."""
        res = _run(HAPPY_CANDIDATE)
        assert res.returncode == 0, res.stderr
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision(HAPPY_CANDIDATE)

    def test_waiver_substring_batch_id_rejects(self) -> None:
        """batch-04 must not inherit the batch-042 waiver substring match."""
        res = _run("CAND-2026-004")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-004")

    def test_holdout_sample_insufficient_rejects(self) -> None:
        """Candidates below the holdout sample minimum must be rejected."""
        res = _run("CAND-2026-093")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-093")

    def test_artifact_manifest_mismatch_rejects(self) -> None:
        """Unregistered artifact digests must be rejected."""
        res = _run("CAND-2026-094")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-094")

    def test_digest_case_insensitive_approves(self) -> None:
        """Uppercase artifact digests must match manifest and compose case-insensitively."""
        res = _run("CAND-2026-045")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-045")


class TestWaiverAndDeterminism:
    """Latency waiver precedence and stable output encoding."""

    def setup_method(self) -> None:
        """Clear output artifacts before each test."""
        _clear_output()

    def test_waiver_raises_latency_ceiling(self) -> None:
        """batch-042 waiver must allow latency above the 45 ms default."""
        assert latency_ceiling_ms("batch-042") == 58.0
        res = _run("CAND-2026-050")
        assert res.returncode == 0, res.stderr
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-050")

    def test_waiver_ceiling_is_exclusive_upper_bound(self) -> None:
        """Latency above the waived ceiling must still breach."""
        res = _run("CAND-2026-051")
        assert res.returncode == 0
        payload = json.loads(OUT.read_text())
        assert payload == expected_decision("CAND-2026-051")

    def test_waiver_expires_after_revert_date(self) -> None:
        """Expired waivers must fall back to the default latency ceiling."""
        clock_path = Path("/app/config/eval-clock.toml")
        original = clock_path.read_text()
        clock_path.write_text('as_of_date = "2026-06-01"\n')
        try:
            res = _run("CAND-2026-050")
            assert res.returncode == 0
            payload = json.loads(OUT.read_text())
            assert payload == expected_decision("CAND-2026-050")
        finally:
            clock_path.write_text(original)

    def test_waiver_inactive_on_revert_date(self) -> None:
        """Waiver must not apply when as_of_date equals the revert date."""
        clock_path = Path("/app/config/eval-clock.toml")
        original = clock_path.read_text()
        clock_path.write_text('as_of_date = "2026-05-01"\n')
        try:
            res = _run("CAND-2026-050")
            assert res.returncode == 0
            payload = json.loads(OUT.read_text())
            assert payload == expected_decision("CAND-2026-050")
        finally:
            clock_path.write_text(original)

    def test_batch_099_waiver_applies(self) -> None:
        """batch-099 waiver email must raise the ceiling to 52 ms."""
        assert latency_ceiling_ms("batch-099") == 52.0
        res = _run("CAND-2026-092")
        assert res.returncode == 0, res.stderr
        payload = json.loads(OUT.read_text())
        assert payload["checks"]["latency_ok"] is True

    def test_output_is_deterministic(self) -> None:
        """Two consecutive runs must emit identical JSON bytes."""
        _run(HAPPY_CANDIDATE)
        first = OUT.read_bytes()
        _run(HAPPY_CANDIDATE)
        second = OUT.read_bytes()
        assert first == second

    def test_schema_required_fields(self) -> None:
        """Output must include every field required by the decision schema."""
        schema = json.loads(DECISION_SCHEMA.read_text())
        required = set(schema["required"])
        _run(HAPPY_CANDIDATE)
        payload = json.loads(OUT.read_text())
        assert required.issubset(payload.keys())

    def test_json_object_keys_sorted_alphabetically(self) -> None:
        """JSON object keys must be sorted alphabetically at every level."""
        _run(HAPPY_CANDIDATE)
        text = OUT.read_text()
        assert text.index('"approved"') < text.index('"candidate_id"') < text.index('"checks"')
        assert text.index('"checks"') < text.index('"reasons"') < text.index('"status"')
        checks = text[text.index('"checks"'): text.index('"reasons"')]
        assert checks.index('"canary_ok"') < checks.index('"compose_ok"')
        assert checks.index('"compose_ok"') < checks.index('"eval_fresh"')
        assert checks.index('"eval_fresh"') < checks.index('"holdout_ok"')
        assert checks.index('"holdout_ok"') < checks.index('"latency_ok"')
        assert checks.index('"latency_ok"') < checks.index('"manifest_ok"')
        assert checks.index('"manifest_ok"') < checks.index('"metrics_ok"')
        assert checks.index('"metrics_ok"') < checks.index('"upstream_tag_present"')
