#!/usr/bin/env ruby
# frozen_string_literal: true

require "net/http"
require "uri"
require "json"
require "rack"
require "rack/mock"
require_relative "../app/flower_vision_app"

# Prefer live server if already up; otherwise exercise the app via Rack mock.
uri = URI("http://127.0.0.1:#{ENV.fetch('PORT', '3000')}/api/v1/predict")
body = { image_id: "rose001" }.to_json

def parse_ok!(data)
  %w[prediction confidence cache_status].each { |k| raise "missing #{k}" unless data.key?(k) }
  raise "bad prediction" unless data["prediction"].is_a?(String) && !data["prediction"].empty?
  raise "bad confidence" unless data["confidence"].is_a?(Numeric)
  raise "bad cache_status" unless %w[hit miss].include?(data["cache_status"])
end

begin
  req = Net::HTTP::Post.new(uri)
  req["content-type"] = "application/json"
  req.body = body
  res = Net::HTTP.start(uri.hostname, uri.port, open_timeout: 1, read_timeout: 5) do |http|
    http.request(req)
  end
  raise "HTTP #{res.code}" unless res.code.to_i == 200
  data = JSON.parse(res.body)
  parse_ok!(data)
  res2 = Net::HTTP.start(uri.hostname, uri.port, open_timeout: 1, read_timeout: 5) do |http|
    http.request(req)
  end
  data2 = JSON.parse(res2.body)
  raise "expected hit on second call" unless data2["cache_status"] == "hit"
  raise "non-deterministic prediction" unless data2["prediction"] == data["prediction"]
  puts "OK api prediction=#{data['prediction']} confidence=#{data['confidence']} (live)"
rescue StandardError
  app = FlowerVisionApp.new
  make = lambda do
    env = Rack::MockRequest.env_for(
      "/api/v1/predict",
      method: "POST",
      input: body,
      "CONTENT_TYPE" => "application/json"
    )
    status, _headers, resp = app.call(env)
    raise "bad status #{status}" unless status == 200
    JSON.parse(resp.join)
  end
  data = make.call
  parse_ok!(data)
  data2 = make.call
  raise "expected hit on second call" unless data2["cache_status"] == "hit"
  raise "non-deterministic prediction" unless data2["prediction"] == data["prediction"]
  puts "OK api prediction=#{data['prediction']} confidence=#{data['confidence']} (rack)"
end
