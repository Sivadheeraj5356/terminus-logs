#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/boot"

redis = FlowerVision.redis
redis.flushdb

fixtures = Dir[File.join(FlowerVision::FIXTURES_DIR, "*.png")].sort
raise "no fixtures" if fixtures.empty?

fixtures.each_with_index do |path, i|
  id = File.basename(path, ".png")
  features = ImageFeatureExtractor.extract(path)
  version = (i % 3 == 0 ? "v1" : "v2")
  expired = (i % 4 == 1)
  entry = {
    "feature_version" => version,
    "checksum" => features[:checksum],
    "width" => features[:width],
    "height" => features[:height],
    "mean_rgb" => features[:mean_rgb],
    "prediction" => FlowerClassifier.predict(features).slice("class", "confidence"),
    "expires_at" => expired ? (Time.now.to_i - 60) : (Time.now.to_i + 86_400)
  }
  entry["checksum"] = "stale#{i}" if i == fixtures.length - 1
  entry["mean_rgb"] = [0, 0, 0] if i == fixtures.length - 2
  legacy_key = (id == "rose001" ? "flower_prediction:alice:#{id}" : "flower_prediction:#{id}")
  redis.set(legacy_key, JSON.generate(entry))
end

redis.set("flower_prediction:broken_json", "{not-json")
redis.set(
  "flower_prediction:missing_meta",
  JSON.generate({ "feature_version" => "v2", "prediction" => { "class" => "x", "confidence" => 0.2 } })
)
redis.set(
  "flower_prediction:old_version",
  JSON.generate(
    {
      "feature_version" => "v0",
      "checksum" => "deadbeef",
      "prediction" => { "class" => "x", "confidence" => 0.2 },
      "mean_rgb" => [1, 2, 3],
      "width" => 10,
      "height" => 10,
      "expires_at" => Time.now.to_i + 86_400
    }
  )
)

puts "Seeded #{redis.keys('flower_prediction:*').size} legacy keys"
