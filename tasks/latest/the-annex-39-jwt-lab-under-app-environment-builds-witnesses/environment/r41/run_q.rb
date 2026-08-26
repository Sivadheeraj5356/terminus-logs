# frozen_string_literal: true
require "json"
require_relative "lane_cache"

base = JSON.parse(ARGV[0])
overlay = JSON.parse(ARGV[1])
ctx = JSON.parse(ARGV[2] || "{}")
out = LaneCache.cached_bind(base: base, overlay: overlay, ctx: ctx)
puts JSON.generate(out)
