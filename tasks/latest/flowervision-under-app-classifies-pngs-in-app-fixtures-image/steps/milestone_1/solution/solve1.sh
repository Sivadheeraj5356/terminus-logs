#!/bin/bash
set -euo pipefail
cd /app

cat > /app/lib/image_feature_extractor.rb <<'RUBY'
# frozen_string_literal: true

require "open3"
require "digest"
require "json"
require "tempfile"

class ImageFeatureExtractor
  TARGET = 224

  def self.extract(image_path)
    raise ArgumentError, "missing image" unless image_path && File.file?(image_path)

    ident_out, _status = Open3.capture2("identify", "-format", "%w %h", image_path.to_s)
    orig_w, orig_h = ident_out.strip.split.map(&:to_i)

    Tempfile.create(["fv", ".rgb"]) do |tmp|
      tmp.close
      cmd = [
        "convert", image_path.to_s,
        "-resize", "#{TARGET}x#{TARGET}!",
        "-depth", "8",
        "rgb:#{tmp.path}"
      ]
      _out, err, status = Open3.capture3(*cmd)
      raise "ImageMagick failed: #{err}" unless status.success?

      bytes = File.binread(tmp.path)
      expected = TARGET * TARGET * 3
      raise "unexpected pixel buffer size #{bytes.bytesize}" unless bytes.bytesize == expected

      sum_r = sum_g = sum_b = 0
      pixels = TARGET * TARGET
      i = 0
      while i < bytes.bytesize
        sum_r += bytes.getbyte(i)
        sum_g += bytes.getbyte(i + 1)
        sum_b += bytes.getbyte(i + 2)
        i += 3
      end

      prefix = "#{orig_w}x#{orig_h}:"
      {
        width: TARGET,
        height: TARGET,
        mean_rgb: [(sum_r / pixels), (sum_g / pixels), (sum_b / pixels)],
        checksum: Digest::SHA256.hexdigest(prefix.b + bytes)
      }
    end
  end
end

class FeatureSerializer
  def self.serialize(features)
    h = features.transform_keys(&:to_sym)
    obj = {
      "width" => h.fetch(:width),
      "height" => h.fetch(:height),
      "mean_rgb" => h.fetch(:mean_rgb),
      "checksum" => h.fetch(:checksum)
    }
    JSON.generate(obj)
  end
end
RUBY

bundle exec ruby /app/scripts/test_features.rb
