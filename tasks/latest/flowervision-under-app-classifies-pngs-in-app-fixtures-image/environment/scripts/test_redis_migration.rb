#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/boot"

redis = FlowerVision.redis
legacy = redis.keys("flower_prediction:*")
raise "legacy keys still present: #{legacy}" unless legacy.empty?

manifest = JSON.parse(File.read(FlowerVision::MANIFEST_PATH))
%w[schema_version migrated removed failed].each { |k| raise "manifest missing #{k}" unless manifest.key?(k) }
raise "schema_version must be 1" unless manifest["schema_version"] == "1"
raise "failed migrations" unless manifest["failed"].to_i.zero?
raise "nothing migrated" unless manifest["migrated"].to_i.positive?
raise "nothing removed" unless manifest["removed"].to_i.positive?

namespaced = redis.keys("ml:v2:model:flower:user:*:image:*")
raise "missing namespaced keys" if namespaced.empty?

namespaced.each do |key|
  raw = redis.get(key)
  entry = JSON.parse(raw)
  raise "invalid cached entry #{key}" unless CacheValidator.valid?(entry)
end

raise "missing user-scoped migrated key" if redis.keys("ml:v2:model:flower:user:alice:image:*").empty?

puts "OK migration manifest=#{manifest.inspect} keys=#{namespaced.size}"
