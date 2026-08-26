#!/bin/bash
set -euo pipefail
cd /app

if ! redis-cli ping >/dev/null 2>&1; then
  redis-server --daemonize yes --port 6379 --bind 127.0.0.1 --save "" --appendonly no
  sleep 1
fi

cat > /app/lib/redis_migration.rb <<'RUBY'
# frozen_string_literal: true

require "json"
require "fileutils"

class RedisKeyBuilder
  def self.build(model:, image_id:, user_id: "default")
    "ml:v2:model:#{model}:user:#{user_id}:image:#{image_id}"
  end
end

class RedisMigration
  LEGACY_PREFIX = "flower_prediction:"

  def self.redis
    FlowerVision.redis
  end

  def self.discover_legacy_keys
    redis.keys("#{LEGACY_PREFIX}*").sort
  end

  def self.parse_legacy(remainder)
    parts = remainder.split(":", 2)
    if parts.length == 1
      ["default", parts[0]]
    else
      [parts[0], parts[1]]
    end
  end

  def self.migrate_key(old_key)
    raise ArgumentError, "not legacy" unless old_key.start_with?(LEGACY_PREFIX)

    remainder = old_key.delete_prefix(LEGACY_PREFIX)
    user_id, image_id = parse_legacy(remainder)
    new_key = RedisKeyBuilder.build(
      model: FlowerVision::MODEL_NAME,
      image_id: image_id,
      user_id: user_id
    )
    value = redis.get(old_key)
    raise "missing value for #{old_key}" if value.nil?

    redis.set(new_key, value)
    redis.del(old_key)
    new_key
  end

  def self.image_path_for(image_id)
    File.join(FlowerVision::FIXTURES_DIR, "#{image_id}.png")
  end

  def self.image_id_from_key(key)
    key.split(":").last
  end

  def self.stale_reason(key, raw)
    begin
      entry = JSON.parse(raw)
    rescue JSON::ParserError
      return "corrupt_json"
    end

    return "missing_checksum" unless entry["checksum"].is_a?(String) && !entry["checksum"].empty?
    return "missing_prediction" unless entry["prediction"].is_a?(Hash)
    return "missing_mean_rgb" unless entry["mean_rgb"].is_a?(Array) && entry["mean_rgb"].length == 3
    return "old_version" unless entry["feature_version"] == FlowerVision::FEATURE_VERSION
    if entry["expires_at"].is_a?(Numeric) && entry["expires_at"].to_i < Time.now.to_i
      return "expired"
    end

    image_id = image_id_from_key(key)
    path = image_path_for(image_id)
    if File.file?(path)
      live = ImageFeatureExtractor.extract(path)
      return "checksum_mismatch" unless entry["checksum"] == live[:checksum]
      return "mean_rgb_mismatch" unless entry["mean_rgb"] == live[:mean_rgb]
    end

    nil
  end

  def self.remove_stale_features
    removed = 0
    pattern = "ml:v2:model:#{FlowerVision::MODEL_NAME}:user:*:image:*"
    redis.keys(pattern).each do |key|
      raw = redis.get(key)
      next if raw.nil?

      reason = stale_reason(key, raw)
      next unless reason

      redis.del(key)
      removed += 1
    end
    removed
  end

  def self.run!
    migrated = 0
    failed = 0
    discover_legacy_keys.each do |old_key|
      begin
        migrate_key(old_key)
        migrated += 1
      rescue StandardError
        failed += 1
      end
    end
    removed = remove_stale_features
    manifest = {
      "schema_version" => "1",
      "migrated" => migrated,
      "removed" => removed,
      "failed" => failed
    }
    FileUtils.mkdir_p(File.dirname(FlowerVision::MANIFEST_PATH))
    File.write(FlowerVision::MANIFEST_PATH, JSON.pretty_generate(manifest) + "\n")
    manifest
  end
end
RUBY

bundle exec ruby /app/scripts/seed_cache.rb
bundle exec ruby /app/scripts/run_migration.rb
bundle exec ruby /app/scripts/test_redis_migration.rb
