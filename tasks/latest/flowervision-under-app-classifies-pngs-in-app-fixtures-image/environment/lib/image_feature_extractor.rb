# frozen_string_literal: true

# BUG: returns non-deterministic / incomplete feature blobs.
# Required: ImageMagick-backed extract + FeatureSerializer.serialize
class ImageFeatureExtractor
  def self.extract(image_path)
    raise NotImplementedError, "ImageFeatureExtractor.extract is incomplete"
  end
end

class FeatureSerializer
  def self.serialize(features)
    raise NotImplementedError, "FeatureSerializer.serialize is incomplete"
  end
end
