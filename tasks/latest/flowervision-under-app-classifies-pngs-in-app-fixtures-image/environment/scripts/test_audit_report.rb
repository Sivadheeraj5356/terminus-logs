#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/boot"

PredictionAudit.generate_report
path = FlowerVision::AUDIT_PATH
raise "missing audit #{path}" unless File.exist?(path)

report = JSON.parse(File.read(path))
%w[total_predictions cache_hits cache_misses invalid_entries_removed feature_version users_seen].each do |k|
  raise "audit missing #{k}" unless report.key?(k)
end
raise "feature_version must be v2" unless report["feature_version"] == "v2"
raise "users_seen must be array" unless report["users_seen"].is_a?(Array)
raise "total_predictions must be > 0" unless report["total_predictions"].to_i.positive?
sum = report["cache_hits"].to_i + report["cache_misses"].to_i
raise "hits+misses != total" unless sum == report["total_predictions"].to_i

puts "OK audit=#{report.inspect}"
