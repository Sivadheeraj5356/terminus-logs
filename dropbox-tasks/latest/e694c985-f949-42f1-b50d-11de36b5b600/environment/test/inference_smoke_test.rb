# frozen_string_literal: true

require_relative "../config/boot"

ok = true
begin
  path = Dir[File.join(FlowerVision::FIXTURES_DIR, "*.png")].sort.first
  f = ImageFeatureExtractor.extract(path)
  ok &&= f[:checksum].is_a?(String)
  key = RedisKeyBuilder.build(model: FlowerVision::MODEL_NAME, image_id: "rose001", user_id: "default")
  ok &&= key == "ml:v2:model:flower:user:default:image:rose001"
  ok &&= CacheValidator.valid?({
    "feature_version" => "v2",
    "checksum" => "abc",
    "mean_rgb" => [1, 2, 3],
    "prediction" => { "class" => "rose", "confidence" => 0.9 },
    "expires_at" => Time.now.to_i + 100
  })
  ok &&= !CacheValidator.valid?("{broken")
rescue StandardError => e
  warn e.message
  ok = false
end

puts(ok ? "rails test OK" : "rails test FAIL")
exit(ok ? 0 : 1)
