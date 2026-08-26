# frozen_string_literal: true

# Deterministic flower labeler from image features (no ML download).
class FlowerClassifier
  LABELS = %w[rose daisy tulip violet sunflower].freeze

  def self.predict(features)
    mean = features.fetch(:mean_rgb)
    checksum = features.fetch(:checksum).to_s
    score = (mean[0].to_i * 3 + mean[1].to_i * 5 + mean[2].to_i * 7 + checksum.bytes.sum) % 10_000
    idx = score % LABELS.length
    confidence = ((score % 400) / 1000.0) + 0.55
    confidence = confidence.round(2)
    confidence = 0.99 if confidence > 0.99
    confidence = 0.55 if confidence < 0.55
    {
      "class" => LABELS[idx],
      "confidence" => confidence,
      "feature_version" => FlowerVision::FEATURE_VERSION
    }
  end
end
