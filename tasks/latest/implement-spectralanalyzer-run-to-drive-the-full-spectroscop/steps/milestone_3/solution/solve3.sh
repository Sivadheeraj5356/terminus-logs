#!/bin/bash
set -euo pipefail

# Replace spectral_analyzer.rb with the full pipeline implementation
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
    # Skip DC bin (index 0) — any residual offset would bias
    # the dominant frequency estimate toward 0 Hz.
    ac_bins = fft_bins.drop(1)
    return 0.0 if ac_bins.empty?
    max_bin = ac_bins.max_by { |b| b['magnitude'] }
    max_bin['frequencyHz']
  end

  def run!
    FileUtils.mkdir_p('/app/output')

    simulation_data = fetch_simulation
    samples = simulation_data['samples']
    fft_bins = simulation_data['fftBins']
    rms_energy = compute_rms_energy(samples)
    dominant_freq = compute_dominant_frequency(simulation_data)
    num_samples = samples ? samples.length : 0

    json_path = "/app/output/#{sensor_id}_analysis.json"
    json_data = {
      sensorId: sensor_id,
      sampleRateHz: sample_rate_hz,
      durationSec: duration_sec,
      damping: damping,
      naturalFreqHz: natural_freq_hz,
      rmsEnergy: rms_energy,
      dominantFrequencyHz: dominant_freq,
      numSamples: num_samples,
      apiMetadata: fetch_metadata
    }
    File.write(json_path, JSON.generate(json_data))

    csv_path = "/app/output/#{sensor_id}_spectrum.csv"
    File.open(csv_path, 'w') do |f|
      f.puts 'frequencyHz,magnitudeDB'
      fft_bins.each do |bin|
        mag_db = 20 * Math.log10([bin['magnitude'], 1e-6].max)
        f.puts "#{bin['frequencyHz']},#{mag_db}"
      end
    end

    File.write('/app/output/manifest.txt', "#{sensor_id}_analysis.json\n#{sensor_id}_spectrum.csv\n")
  end
end
RUBY

cd /app && ruby -e "
require '/app/lib/spectral_analyzer'
sa = SpectralAnalyzer.new
sa.run!
puts 'Analysis complete'
"

echo "Artifact files:"
cat /app/output/manifest.txt
