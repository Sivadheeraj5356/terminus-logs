#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/boot"

RedisMigration.run!
puts "Migration complete: #{FlowerVision::MANIFEST_PATH}"
puts File.read(FlowerVision::MANIFEST_PATH)
