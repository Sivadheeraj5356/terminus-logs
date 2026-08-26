#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/boot"

path = Dir[File.join(FlowerVision::FIXTURES_DIR, "*.png")].sort.first
raise "missing fixture" unless path

f1 = ImageFeatureExtractor.extract(path)
f2 = ImageFeatureExtractor.extract(path)

raise "missing width" unless f1[:width].is_a?(Integer) && f1[:width] > 0
raise "missing height" unless f1[:height].is_a?(Integer) && f1[:height] > 0
raise "mean_rgb invalid" unless f1[:mean_rgb].is_a?(Array) && f1[:mean_rgb].size == 3
raise "checksum missing" unless f1[:checksum].is_a?(String) && f1[:checksum].length >= 8
raise "checksum unstable" unless f1[:checksum] == f2[:checksum]
raise "features unstable" unless f1 == f2

json1 = FeatureSerializer.serialize(f1)
json2 = FeatureSerializer.serialize(f2)
raise "serializer non-deterministic" unless json1 == json2

parsed = JSON.parse(json1)
%w[width height mean_rgb checksum].each do |k|
  raise "missing key #{k}" unless parsed.key?(k)
end
# Stable field order: width, height, mean_rgb, checksum
order = json1.scan(/"(\w+)"\s*:/).flatten
expected_order = %w[width height mean_rgb checksum]
raise "bad field order #{order}" unless order == expected_order
raise "timestamps forbidden" if json1.include?("timestamp") || json1.include?("created_at")

puts "OK features checksum=#{f1[:checksum]} size=#{f1[:width]}x#{f1[:height]}"
