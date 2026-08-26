#!/bin/bash
set -euo pipefail

# Patch spectral_analyzer.rb: implement parse_containerfile
# The current stub returns {} — replace with a real parser.
cat > /app/lib/spectral_analyzer.rb << 'RUBY'
#!/usr/bin/env ruby

require 'net/http'
require 'json'
require 'csv'
require 'fileutils'

class SpectralAnalyzer
  attr_reader :params, :api_base

  def initialize(containerfile_path = '/app/Containerfile', api_base = 'http://localhost:3000')
    @params = parse_containerfile(containerfile_path)
    @api_base = api_base
  end

  def parse_containerfile(path)
    return {} unless File.file?(path)

    params = {}
    File.readlines(path).each do |line|
      line = line.strip
      next if line.empty? || line.start_with?('#')

      if line.match(/^(\w[\w_]*)\s*=\s*(.*)$/)
        key = $1
        value = $2.strip
        value = value.to_f if value.to_f.to_s == value
        params[key.downcase.to_sym] = value
      end
    end

    params
  end

  def sample_rate_hz
    @params[:sensor_frequency_hz]
  end

  def duration_sec
    @params[:sample_duration_sec]
  end

  def damping
    @params[:damping_coefficient]
  end

  def natural_freq_hz
    @params[:natural_frequency_hz]
  end

  def sensor_id
    @params[:sensor_id]
  end

  def fetch_simulation
    uri = URI("#{@api_base}/simulate")
    http = Net::HTTP.new(uri.host, uri.port)
    req = Net::HTTP::Post.new(uri.path, { 'Content-Type' => 'application/json' })
    req.body = {
      sampleRateHz: sample_rate_hz,
      durationSec: duration_sec,
      damping: damping,
      naturalFreqHz: natural_freq_hz
    }.to_json
    res = http.request(req)
    JSON.parse(res.body)
  end

  def api_healthy?
    uri = URI("#{@api_base}/health")
    res = Net::HTTP.get_response(uri)
    data = JSON.parse(res.body)
    data['status'] == 'ok'
  rescue
    false
  end

  def fetch_metadata
    uri = URI("#{@api_base}/metadata")
    res = Net::HTTP.get_response(uri)
    JSON.parse(res.body)
  end

  def compute_rms_energy(samples)
    return 0.0 if samples.nil? || samples.empty?
    mean = samples.sum / samples.size.to_f
    squared = samples.map { |s| (s - mean) ** 2 }
    Math.sqrt(squared.sum / squared.size.to_f)
  end

  def compute_dominant_frequency(simulation_data)
    fft_bins = simulation_data['fftBins']
    return 0.0 if fft_bins.nil? || fft_bins.empty?
    max_bin = fft_bins.max_by { |b| b['magnitude'] }
    max_bin['frequencyHz']
  end

  def run!
    FileUtils.mkdir_p('/app/output')
  end
end
RUBY

# Create parse_spec.rb executable that uses the library
mkdir -p /app/bin
cat > /app/bin/parse_spec.rb << 'SCRIPT'
#!/usr/bin/env ruby
require '/app/lib/spectral_analyzer'

path = ARGV[0] || '/app/Containerfile'

unless File.file?(path)
  $stderr.puts "Error: File not found: #{path}"
  exit(1)
end

sa = SpectralAnalyzer.new(path)
sa.params.each do |key, value|
  puts "#{key}: #{value}"
end
exit(0)
SCRIPT

chmod +x /app/bin/parse_spec.rb
