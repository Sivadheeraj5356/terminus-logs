"""Milestone 2 verifiers for Redis key migration and stale feature cleanup."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


MANIFEST = Path("/tmp/redis_migration_manifest.json")


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


def _redis(cmd: list[str]) -> str:
    proc = subprocess.run(
        ["redis-cli", *cmd], capture_output=True, text=True, check=True, timeout=30
    )
    return proc.stdout.strip()


class TestMilestone2:
    """Namespaced Redis migration and stale-entry removal."""

    def test_key_builder_user_namespace(self) -> None:
        """RedisKeyBuilder.build must emit ml:v2:model:<model>:user:<user>:image:<id> keys."""
        out = _ruby(
            """
require_relative '/app/config/boot'
puts RedisKeyBuilder.build(model: 'flower', image_id: 'rose001', user_id: 'alice')
"""
        )
        assert out == "ml:v2:model:flower:user:alice:image:rose001"

    def test_migration_script_suite_passes(self) -> None:
        """Seed + run_migration + test_redis_migration scripts must succeed."""
        _ensure_redis()
        for script in (
            "/app/scripts/seed_cache.rb",
            "/app/scripts/run_migration.rb",
            "/app/scripts/test_redis_migration.rb",
        ):
            proc = subprocess.run(
                ["bundle", "exec", "ruby", script],
                cwd="/app",
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            assert proc.returncode == 0, f"{script} failed:\n{proc.stderr}\n{proc.stdout}"

    def test_manifest_schema_version_and_counts(self) -> None:
        """Migration manifest includes schema_version 1 and integer migrated/removed/failed."""
        assert MANIFEST.is_file(), "missing migration manifest"
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assert data.get("schema_version") == "1"
        for key in ("migrated", "removed", "failed"):
            assert key in data
            assert isinstance(data[key], int)
        assert data["failed"] == 0
        assert data["migrated"] > 0
        assert data["removed"] > 0

    def test_no_legacy_keys_remain(self) -> None:
        """After migration, flower_prediction:* keys must be gone."""
        _ensure_redis()
        keys = _redis(["keys", "flower_prediction:*"])
        assert keys in ("", "(empty list or set)")

    def test_user_scoped_legacy_key_migrated(self) -> None:
        """flower_prediction:<user>:<image_id> legacy keys migrate under that user scope."""
        _ensure_redis()
        val = _redis(["get", "ml:v2:model:flower:user:alice:image:rose001"])
        assert val not in ("", "(nil)")

    def test_stale_corrupt_and_old_version_removed(self) -> None:
        """broken_json, missing_meta, and old_version legacy ids must not survive."""
        _ensure_redis()
        for bad in ("broken_json", "missing_meta", "old_version"):
            val = _redis(["get", f"ml:v2:model:flower:user:default:image:{bad}"])
            assert val in ("", "(nil)"), f"stale key survived for {bad}: {val}"

    def test_mean_rgb_mismatch_removed(self) -> None:
        """Entries with mean_rgb that diverges from live extraction are removed as stale."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
path = Dir['/app/fixtures/images/*.png'].sort.first
image_id = File.basename(path, '.png')
key = RedisKeyBuilder.build(model: 'flower', image_id: image_id, user_id: 'default')
live = ImageFeatureExtractor.extract(path)
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v2',
  'checksum' => live[:checksum],
  'mean_rgb' => [9, 9, 9],
  'width' => live[:width],
  'height' => live[:height],
  'prediction' => {'class' => 'rose', 'confidence' => 0.5},
  'expires_at' => Time.now.to_i + 3600
}))
removed = RedisMigration.remove_stale_features
val = FlowerVision.redis.get(key)
puts JSON.generate({'removed' => removed, 'gone' => val.nil?})
"""
        )
        data = json.loads(out)
        assert data["removed"] >= 1
        assert data["gone"] is True

    def test_expired_entry_removed(self) -> None:
        """An expired v2 cache entry must be deleted by remove_stale_features."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
path = File.join(FlowerVision::FIXTURES_DIR, 'daisy002.png')
live = ImageFeatureExtractor.extract(path)
key = RedisKeyBuilder.build(model: 'flower', image_id: 'daisy002', user_id: 'default')
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v2',
  'checksum' => live[:checksum],
  'mean_rgb' => live[:mean_rgb],
  'width' => live[:width],
  'height' => live[:height],
  'prediction' => {'class' => 'rose', 'confidence' => 0.5},
  'expires_at' => Time.now.to_i - 60
}))
removed = RedisMigration.remove_stale_features
puts JSON.generate({'removed' => removed, 'gone' => FlowerVision.redis.get(key).nil?})
"""
        )
        data = json.loads(out)
        assert data["removed"] >= 1
        assert data["gone"] is True

    def test_checksum_mismatch_removed(self) -> None:
        """A v2 entry with wrong checksum must be deleted by remove_stale_features."""
        _ensure_redis()
        out = _ruby(
            """
require_relative '/app/config/boot'
path = File.join(FlowerVision::FIXTURES_DIR, 'tulip003.png')
live = ImageFeatureExtractor.extract(path)
key = RedisKeyBuilder.build(model: 'flower', image_id: 'tulip003', user_id: 'default')
FlowerVision.redis.set(key, JSON.generate({
  'feature_version' => 'v2',
  'checksum' => 'deadbeef' + ('0' * 56),
  'mean_rgb' => live[:mean_rgb],
  'width' => live[:width],
  'height' => live[:height],
  'prediction' => {'class' => 'rose', 'confidence' => 0.5},
  'expires_at' => Time.now.to_i + 3600
}))
removed = RedisMigration.remove_stale_features
puts JSON.generate({'removed' => removed, 'gone' => FlowerVision.redis.get(key).nil?})
"""
        )
        data = json.loads(out)
        assert data["removed"] >= 1
        assert data["gone"] is True

    def test_injection_recreate_migration(self) -> None:
        """Deleting manifest and re-running migration after reseeding remains successful."""
        _ensure_redis()
        if MANIFEST.exists():
            before = json.loads(MANIFEST.read_text(encoding="utf-8"))
            MANIFEST.unlink()
        else:
            before = None
        for script in ("/app/scripts/seed_cache.rb", "/app/scripts/run_migration.rb"):
            proc = subprocess.run(
                ["bundle", "exec", "ruby", script],
                cwd="/app",
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            assert proc.returncode == 0, proc.stderr + proc.stdout
        assert MANIFEST.is_file()
        after = json.loads(MANIFEST.read_text(encoding="utf-8"))
        assert after["schema_version"] == "1"
        assert after["failed"] == 0
        assert after["migrated"] > 0
        assert after["removed"] > 0
        if before is not None:
            assert after["migrated"] == before["migrated"]
