# frozen_string_literal: true

# Broken inference path: ignores migration layer and returns stale shape.
class InferenceService
  def self.predict(image_id:)
    {
      "class" => "unknown",
      "confidence" => 0.0,
      "feature_version" => "v0",
      "cache" => "miss"
    }
  end
end
