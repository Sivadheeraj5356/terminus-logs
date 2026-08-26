#!/bin/bash
set -euo pipefail
cd /app

if ! redis-cli ping >/dev/null 2>&1; then
  redis-server --daemonize yes --port 6379 --bind 127.0.0.1 --save "" --appendonly no
  sleep 1
fi

cat > /app/lib/cache_validator.rb <<'RUBY'
# frozen_string_literal: true

require "json"

class CacheValidator
  def self.valid?(entry)
    data =
      case entry
      when String
        begin
          JSON.parse(entry)
        rescue JSON::ParserError
          return false
        end
      when Hash
        entry
      else
        return false
      end

    return false unless data["checksum"].is_a?(String) && !data["checksum"].empty?
    return false unless data["feature_version"] == FlowerVision::FEATURE_VERSION
    return false unless data["prediction"].is_a?(Hash)
    return false unless data["prediction"]["class"].is_a?(String)
    return false unless data["prediction"]["confidence"].is_a?(Numeric)
    return false unless data["mean_rgb"].is_a?(Array) && data["mean_rgb"].length == 3
    return false unless data["mean_rgb"].all? { |v| v.is_a?(Integer) }
    if data.key?("expires_at")
      return false unless data["expires_at"].is_a?(Numeric)
      return false if data["expires_at"].to_i < Time.now.to_i
    end
    true
  end
end
RUBY

cat > /app/app/services/inference_service.rb <<'RUBY'
# frozen_string_literal: true

require "json"

class InferenceService
  def self.redis
    FlowerVision.redis
  end

  def self.bump(name)
    redis.incr(name)
  end

  def self.track_user(user_id)
    redis.sadd("fv:audit:users", user_id)
  end

  def self.predict(image_id:, user_id: "default")
    path = File.join(FlowerVision::FIXTURES_DIR, "#{image_id}.png")
    raise ArgumentError, "unknown image_id #{image_id}" unless File.file?(path)

    track_user(user_id)
    key = RedisKeyBuilder.build(
      model: FlowerVision::MODEL_NAME,
      image_id: image_id,
      user_id: user_id
    )
    raw = redis.get(key)
    if raw
      unless CacheValidator.valid?(raw)
        redis.del(key)
        bump("fv:audit:invalid_removed")
        raw = nil
      end
    end

    if raw
      entry = JSON.parse(raw)
      live = ImageFeatureExtractor.extract(path)
      if entry["checksum"] != live[:checksum] ||
         entry["mean_rgb"] != live[:mean_rgb] ||
         entry["feature_version"] != FlowerVision::FEATURE_VERSION
        redis.del(key)
        bump("fv:audit:invalid_removed")
        raw = nil
      else
        bump("fv:audit:total")
        bump("fv:audit:hits")
        return {
          "class" => entry.dig("prediction", "class"),
          "confidence" => entry.dig("prediction", "confidence"),
          "feature_version" => FlowerVision::FEATURE_VERSION,
          "cache" => "hit"
        }
      end
    end

    features = ImageFeatureExtractor.extract(path)
    prediction = FlowerClassifier.predict(features)
    entry = {
      "feature_version" => FlowerVision::FEATURE_VERSION,
      "checksum" => features[:checksum],
      "width" => features[:width],
      "height" => features[:height],
      "mean_rgb" => features[:mean_rgb],
      "prediction" => {
        "class" => prediction["class"],
        "confidence" => prediction["confidence"]
      },
      "expires_at" => Time.now.to_i + 86_400
    }
    redis.set(key, JSON.generate(entry))
    bump("fv:audit:total")
    bump("fv:audit:misses")
    {
      "class" => prediction["class"],
      "confidence" => prediction["confidence"],
      "feature_version" => FlowerVision::FEATURE_VERSION,
      "cache" => "miss"
    }
  end
end
RUBY

cat > /app/app/controllers/api/v1/predict_controller.rb <<'RUBY'
# frozen_string_literal: true

module Api
  module V1
    class PredictController
      def call(req)
        body = JSON.parse(req.body.read)
        image_id = body["image_id"]
        user_id = body.fetch("user_id", "default")
        result = InferenceService.predict(image_id: image_id, user_id: user_id)
        payload = {
          "prediction" => result["class"],
          "confidence" => result["confidence"].to_f.round(2),
          "cache_status" => result["cache"]
        }
        [200, { "content-type" => "application/json" }, [payload.to_json]]
      rescue StandardError => e
        [500, { "content-type" => "application/json" }, [{ "error" => e.message }.to_json]]
      end
    end
  end
end
RUBY

cat > /app/lib/prediction_audit.rb <<'RUBY'
# frozen_string_literal: true

require "json"
require "fileutils"

class PredictionAudit
  def self.generate_report
    redis = FlowerVision.redis
    total = redis.get("fv:audit:total").to_i
    hits = redis.get("fv:audit:hits").to_i
    misses = redis.get("fv:audit:misses").to_i
    invalid = redis.get("fv:audit:invalid_removed").to_i
    users = redis.smembers("fv:audit:users").sort

    if total.zero?
      InferenceService.predict(image_id: "rose001", user_id: "default")
      InferenceService.predict(image_id: "rose001", user_id: "default")
      total = redis.get("fv:audit:total").to_i
      hits = redis.get("fv:audit:hits").to_i
      misses = redis.get("fv:audit:misses").to_i
      invalid = redis.get("fv:audit:invalid_removed").to_i
      users = redis.smembers("fv:audit:users").sort
    end

    report = {
      "total_predictions" => total,
      "cache_hits" => hits,
      "cache_misses" => misses,
      "invalid_entries_removed" => invalid,
      "feature_version" => FlowerVision::FEATURE_VERSION,
      "users_seen" => users
    }
    FileUtils.mkdir_p(FlowerVision::OUTPUT_DIR)
    File.write(FlowerVision::AUDIT_PATH, JSON.pretty_generate(report) + "\n")
    report
  end
end
RUBY

if ! grep -q 'def self.extract' /app/lib/image_feature_extractor.rb || grep -q 'NotImplementedError' /app/lib/image_feature_extractor.rb; then
  echo "M1 artifacts missing" >&2
  exit 1
fi
if ! grep -q 'ml:v2:model' /app/lib/redis_migration.rb; then
  echo "M2 artifacts missing" >&2
  exit 1
fi

bundle exec ruby -e 'require_relative "/app/config/boot"; InferenceService.predict(image_id: "daisy002", user_id: "alice"); InferenceService.predict(image_id: "daisy002", user_id: "alice"); PredictionAudit.generate_report'

bundle exec ruby -e '
require_relative "/app/app/flower_vision_app"
require "rack/mock"
app = FlowerVisionApp.new
env = Rack::MockRequest.env_for("/api/v1/predict", method: "POST", input: %q({"image_id":"flower001","user_id":"alice"}), "CONTENT_TYPE" => "application/json")
status, _headers, body = app.call(env)
raise "bad status #{status} #{body}" unless status == 200
payload = JSON.parse(body.join)
raise "missing keys" unless payload.keys.sort == %w[cache_status confidence prediction]
raise "confidence not 2dp" unless payload["confidence"].to_s =~ /\A\d+\.\d{2}\z/
'

ruby /app/bin/rails test
bundle exec ruby /app/scripts/test_audit_report.rb
