"""Milestone 3 verifiers for inference API hardening and audit reporting."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


AUDIT = Path("/app/output/inference_audit.json")


def _ensure_redis() -> None:
    ping = subprocess.run(
        ["redis-cli", "ping"], capture_output=True, text=True, check=False
    )
    if ping.returncode != 0 or "PONG" not in ping.stdout:
        subprocess.run(
            [
                "redis-server",
                "--daemonize",
                "yes",
                "--port",
                "6379",
                "--bind",
                "127.0.0.1",
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            check=True,
            timeout=30,
        )


def _ruby(code: str) -> str:
    proc = subprocess.run(
        ["bundle", "exec", "ruby", "-e", code],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert proc.returncode == 0, f"ruby failed:\n{proc.stderr}\n{proc.stdout}"
    return proc.stdout.strip()


class TestMilestone3:
    """Inference service, cache validation, API, and audit report."""

    def test_prior_artifacts_present(self) -> None:
        """Feature extraction and user-scoped key building from earlier milestones must work."""
        out = _ruby(
            """
require_relative '/app/config/boot'
path = Dir['/app/fixtures/images/*.png'].sort.first
f = ImageFeatureExtractor.extract(path)
key = RedisKeyBuilder.build(model: 'flower', image_id: 'rose001', user_id: 'alice')
puts JSON.generate({'checksum' => f[:checksum], 'key' => key, 'w' => f[:width]})
"""
        )
        data = json.loads(out)
        assert data["w"] == 224
        assert isinstance(data["checksum"], str) and len(data["checksum"]) >= 32
        assert data["key"] == "ml:v2:model:flower:user:alice:image:rose001"

    def test_cache_validator_rejects_bad_entries(self) -> None:
        """CacheValidator.valid? rejects corrupt JSON, old versions, missing checksum/mean_rgb, expired."""
        out = _ruby(
            """
require_relative '/app/config/boot'
checks = {
  'ok' => CacheValidator.valid?({
    'feature_version' => 'v2',
    'checksum' => 'abc',
    'mean_rgb' => [1, 2, 3],
    'prediction' => {'class' => 'rose', 'confidence' => 0.9},
    'expires_at' => Time.now.to_i + 100
  }),
  'corrupt' => CacheValidator.valid?('{nope'),
  'old' => CacheValidator.valid?({
    'feature_version' => 'v1',
    'checksum' => 'abc',
    'mean_rgb' => [1, 2, 3],
    'prediction' => {'class' => 'rose', 'confidence' => 0.9},
    'expires_at' => Time.now.to_i + 100
  }),
  'missing_checksum' => CacheValidator.valid?({
    'feature_version' => 'v2',
    'mean_rgb' => [1, 2, 3],
    'prediction' => {'class' => 'rose', 'confidence' => 0.9},
    'expires_at' => Time.now.to_i + 100
  }),
  'missing_mean_rgb' => CacheValidator.valid?({
    'feature_version' => 'v2',
    'checksum' => 'abc',
    'prediction' => {'class' => 'rose', 'confidence' => 0.9},
    'expires_at' => Time.now.to_i + 100
  }),
  'expired' => CacheValidator.valid?({
    'feature_version' => 'v2',
    'checksum' => 'abc',
    'mean_rgb' => [1, 2, 3],
    'prediction' => {'class' => 'rose', 'confidence' => 0.9},
    'expires_at' => Time.now.to_i - 10
  })
}
puts JSON.generate(checks)
"""
        )
        data = json.loads(out)
        assert data["ok"] is True
        assert data["corrupt"] is False
        assert data["old"] is False
        assert data["missing_checksum"] is False
        assert data["missing_mean_rgb"] is False
        assert data["expired"] is False

    def test_predict_miss_then_hit(self) -> None:
        """InferenceService.predict misses then hits with identical class/confidence."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
key = RedisKeyBuilder.build(model: 'flower', image_id: 'tulip003', user_id: 'default')
FlowerVision.redis.del(key)
a = InferenceService.predict(image_id: 'tulip003', user_id: 'default')
b = InferenceService.predict(image_id: 'tulip003', user_id: 'default')
puts JSON.generate({'a' => a, 'b' => b})
"""
        )
        data = json.loads(out)
        assert data["a"]["cache"] == "miss"
        assert data["b"]["cache"] == "hit"
        assert data["a"]["class"] == data["b"]["class"]
        assert data["a"]["confidence"] == data["b"]["confidence"]
        assert data["a"]["feature_version"] == "v2"

    def test_user_cache_isolation(self) -> None:
        """Separate user_id values must not share the same Redis cache entry."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
FlowerVision.redis.flushdb
InferenceService.predict(image_id: 'flower001', user_id: 'alice')
InferenceService.predict(image_id: 'flower001', user_id: 'bob')
k1 = RedisKeyBuilder.build(model: 'flower', image_id: 'flower001', user_id: 'alice')
k2 = RedisKeyBuilder.build(model: 'flower', image_id: 'flower001', user_id: 'bob')
puts JSON.generate({'k1' => k1, 'k2' => k2, 'both' => FlowerVision.redis.exists(k1, k2)})
"""
        )
        data = json.loads(out)
        assert data["k1"] != data["k2"]
        assert data["both"] == 2

    def test_predict_rejects_stale_cache(self) -> None:
        """A deliberately stale cached entry must be discarded and regenerate as a miss."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
key = RedisKeyBuilder.build(model: 'flower', image_id: 'violet004', user_id: 'default')
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v1',
  'checksum' => 'stale',
  'mean_rgb' => [1, 2, 3],
  'prediction' => {'class' => 'bogus', 'confidence' => 0.11},
  'expires_at' => Time.now.to_i + 1000
}))
r = InferenceService.predict(image_id: 'violet004', user_id: 'default')
puts JSON.generate(r)
"""
        )
        data = json.loads(out)
        assert data["cache"] == "miss"
        assert data["class"] != "bogus"
        assert data["feature_version"] == "v2"

    def test_predict_rejects_checksum_mismatch(self) -> None:
        """A v2 cache entry with wrong checksum for a real image must regenerate as a miss."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
path = File.join(FlowerVision::FIXTURES_DIR, 'daisy002.png')
live = ImageFeatureExtractor.extract(path)
key = RedisKeyBuilder.build(model: 'flower', image_id: 'daisy002', user_id: 'default')
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v2',
  'checksum' => 'deadbeef' + ('0' * 56),
  'mean_rgb' => live[:mean_rgb],
  'width' => live[:width],
  'height' => live[:height],
  'prediction' => {'class' => 'bogus', 'confidence' => 0.11},
  'expires_at' => Time.now.to_i + 1000
}))
r = InferenceService.predict(image_id: 'daisy002', user_id: 'default')
puts JSON.generate(r)
"""
        )
        data = json.loads(out)
        assert data["cache"] == "miss"
        assert data["class"] != "bogus"
        assert data["feature_version"] == "v2"

    def test_predict_rejects_mean_rgb_mismatch(self) -> None:
        """A v2 cache entry with wrong mean_rgb for a real image must regenerate as a miss."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
path = File.join(FlowerVision::FIXTURES_DIR, 'tulip003.png')
live = ImageFeatureExtractor.extract(path)
key = RedisKeyBuilder.build(model: 'flower', image_id: 'tulip003', user_id: 'default')
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v2',
  'checksum' => live[:checksum],
  'mean_rgb' => [9, 9, 9],
  'width' => live[:width],
  'height' => live[:height],
  'prediction' => {'class' => 'bogus', 'confidence' => 0.11},
  'expires_at' => Time.now.to_i + 1000
}))
r = InferenceService.predict(image_id: 'tulip003', user_id: 'default')
puts JSON.generate(r)
"""
        )
        data = json.loads(out)
        assert data["cache"] == "miss"
        assert data["class"] != "bogus"
        assert data["feature_version"] == "v2"

    def test_invalid_entries_removed_increments(self) -> None:
        """Seeding an invalid cache entry then predicting must bump invalid_entries_removed."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
FlowerVision.redis.flushdb
FlowerVision.redis.del('fv:audit:invalid_removed', 'fv:audit:total', 'fv:audit:hits', 'fv:audit:misses')
key = RedisKeyBuilder.build(model: 'flower', image_id: 'rose001', user_id: 'default')
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v1',
  'checksum' => 'stale',
  'mean_rgb' => [1, 2, 3],
  'prediction' => {'class' => 'bogus', 'confidence' => 0.11},
  'expires_at' => Time.now.to_i + 1000
}))
before = FlowerVision.redis.get('fv:audit:invalid_removed').to_i
InferenceService.predict(image_id: 'rose001', user_id: 'default')
PredictionAudit.generate_report
report = JSON.parse(File.read(FlowerVision::AUDIT_PATH))
puts JSON.generate({
  'before' => before,
  'invalid_entries_removed' => report['invalid_entries_removed']
})
"""
        )
        data = json.loads(out)
        assert data["before"] == 0
        assert data["invalid_entries_removed"] >= 1

    def test_api_endpoint_contract(self) -> None:
        """POST /api/v1/predict returns real prediction, two-decimal confidence, cache_status."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/app/flower_vision_app'
require 'rack/mock'
app = FlowerVisionApp.new
env = Rack::MockRequest.env_for(
  '/api/v1/predict',
  method: 'POST',
  input: '{"image_id":"flower001","user_id":"alice"}',
  'CONTENT_TYPE' => 'application/json'
)
status, _headers, body = app.call(env)
payload = JSON.parse(body.join)
puts JSON.generate({'status' => status, 'payload' => payload})
"""
        )
        data = json.loads(out)
        assert data["status"] == 200
        payload = data["payload"]
        assert set(payload.keys()) == {"prediction", "confidence", "cache_status"}
        assert isinstance(payload["prediction"], str) and payload["prediction"]
        assert payload["prediction"] != "unknown"
        assert isinstance(payload["confidence"], (int, float))
        assert re.match(r"^\d+\.\d{2}$", f"{payload['confidence']:.2f}")
        assert payload["cache_status"] in ("hit", "miss")

    def test_api_defaults_user_id(self) -> None:
        """POST with only image_id must succeed and write the default-user cache key."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/app/flower_vision_app'
require 'rack/mock'
FlowerVision.redis.flushdb
app = FlowerVisionApp.new
env = Rack::MockRequest.env_for(
  '/api/v1/predict',
  method: 'POST',
  input: '{"image_id":"rose001"}',
  'CONTENT_TYPE' => 'application/json'
)
status, _headers, body = app.call(env)
payload = JSON.parse(body.join)
key = RedisKeyBuilder.build(model: 'flower', image_id: 'rose001', user_id: 'default')
puts JSON.generate({
  'status' => status,
  'payload' => payload,
  'key' => key,
  'cached' => !FlowerVision.redis.get(key).nil?
})
"""
        )
        data = json.loads(out)
        assert data["status"] == 200
        assert set(data["payload"].keys()) == {"prediction", "confidence", "cache_status"}
        assert data["key"] == "ml:v2:model:flower:user:default:image:rose001"
        assert data["cached"] is True

    def test_rails_test_passes(self) -> None:
        """`ruby /app/bin/rails test` must exit 0."""
        _ensure_redis()
        proc = subprocess.run(
            ["ruby", "/app/bin/rails", "test"],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout

    def test_audit_report_shape(self) -> None:
        """Audit report includes counters, feature_version v2, and sorted users_seen."""
        _ensure_redis()
        _ruby(
            """
require_relative '/app/config/boot'
InferenceService.predict(image_id: 'rose001', user_id: 'alice')
InferenceService.predict(image_id: 'rose001', user_id: 'alice')
PredictionAudit.generate_report
"""
        )
        assert AUDIT.is_file()
        report = json.loads(AUDIT.read_text(encoding="utf-8"))
        for key in (
            "total_predictions",
            "cache_hits",
            "cache_misses",
            "invalid_entries_removed",
            "feature_version",
            "users_seen",
        ):
            assert key in report
        assert report["feature_version"] == "v2"
        assert isinstance(report["users_seen"], list)
        assert report["users_seen"] == sorted(report["users_seen"])
        assert report["total_predictions"] > 0
        assert (
            report["cache_hits"] + report["cache_misses"] == report["total_predictions"]
        )

    def test_audit_script_passes(self) -> None:
        """`bundle exec ruby /app/scripts/test_audit_report.rb` must succeed."""
        _ensure_redis()
        proc = subprocess.run(
            ["bundle", "exec", "ruby", "/app/scripts/test_audit_report.rb"],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout

    def test_determinism_across_images(self) -> None:
        """Same image_id and user_id always yield the same prediction class across calls."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
FlowerVision.redis.flushdb
r1 = InferenceService.predict(image_id: 'daisy002', user_id: 'default')
r2 = InferenceService.predict(image_id: 'daisy002', user_id: 'default')
r3 = InferenceService.predict(image_id: 'daisy002', user_id: 'default')
puts JSON.generate([r1['class'], r2['class'], r3['class'], r2['cache'], r3['cache']])
"""
        )
        classes = json.loads(out)
        assert classes[0] == classes[1] == classes[2]
        assert classes[3] == "hit"
        assert classes[4] == "hit"
