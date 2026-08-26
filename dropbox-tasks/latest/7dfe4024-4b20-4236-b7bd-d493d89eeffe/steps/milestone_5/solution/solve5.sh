#!/bin/bash
set -euo pipefail

# Overwrite spectral_analyzer.rb with complete M3 + M4 + M5 implementation.
# This includes the pipeline, validation, diagnostics, and interpolation.

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
    peak_idx = fft_bins.index(max_bin)
    n = fft_bins.length * 2
    sr = sample_rate_hz

    # Edge case: peak at index 0 or N/2-1 => no interpolation
    if peak_idx <= 0 || peak_idx >= fft_bins.length - 1
      store_interp_data(fft_bins, peak_idx, max_bin, max_bin['frequencyHz'])
      return max_bin['frequencyHz']
    end

    m_left  = fft_bins[peak_idx - 1]['magnitude']
    m_peak  = max_bin['magnitude']
    m_right = fft_bins[peak_idx + 1]['magnitude']

    if m_left <= 0 || m_peak <= 0 || m_right <= 0
      store_interp_data(fft_bins, peak_idx, max_bin, max_bin['frequencyHz'])
      return max_bin['frequencyHz']
    end

    log_left = Math.log(m_left)
    log_peak = Math.log(m_peak)
    log_right = Math.log(m_right)

    denom = log_left - 2.0 * log_peak + log_right
    if denom.abs < 1e-12
      store_interp_data(fft_bins, peak_idx, max_bin, max_bin['frequencyHz'])
      return max_bin['frequencyHz']
    end

    delta = 0.5 * (log_left - log_right) / denom
    peak_freq = (peak_idx + delta) * sr / n

    store_interp_data(fft_bins, peak_idx, max_bin, peak_freq)
    peak_freq
  end

  def store_interp_data(fft_bins, peak_idx, max_bin, interpolated_freq)
    @_interp = {
      peak_idx: peak_idx,
      peak_bin_freq: max_bin['frequencyHz'],
      left_mag:  peak_idx > 0 ? fft_bins[peak_idx - 1]['magnitude'] : nil,
      peak_mag:  max_bin['magnitude'],
      right_mag: peak_idx < fft_bins.length - 1 ? fft_bins[peak_idx + 1]['magnitude'] : nil,
      interpolated_freq: interpolated_freq
    }
  end

  def validate_config
    ranges = {
      sensor_frequency_hz: 100..10000,
      sample_duration_sec: 0.1..60.0,
      damping_coefficient: 0.0..1.0,
      natural_frequency_hz: 1..1000
    }
    errors = []
    ranges.each do |key, range|
      val = @params[key]
      errors << "#{key} (#{val}) outside range #{range}" if val && !range.include?(val)
    end
    sr = @params[:sensor_frequency_hz]
    nf = @params[:natural_frequency_hz]
    if sr && nf && nf > sr / 2.0
      errors << "natural_frequency_hz (#{nf}) exceeds Nyquist limit (#{sr / 2.0} Hz)"
    end
    if @params[:sensor_id] && !@params[:sensor_id].match?(/^ACCEL-\d{3}$/)
      errors << "sensor_id (#{@params[:sensor_id]}) must match ACCEL-XXX"
    end
    { valid: errors.empty?, errors: errors }
  end

  def generate_debug_report(data = nil)
    report = {
      parameters: @params,
      validation: validate_config,
      timestamp: Time.now.utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    report[:simulation_data] = data if data
    File.write('/app/debug_report.json', JSON.pretty_generate(report))
    report
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

    # Write interpolation report
    interp = @_interp || {}
    File.open('/app/output/interpolation_report.txt', 'w') do |f|
      f.puts "Peak bin index: #{interp[:peak_idx]}"
      f.puts "Peak bin frequency: #{format('%.4f', interp[:peak_bin_freq] || 0)} Hz"
      f.puts "Left neighbor magnitude: #{format('%.8f', interp[:left_mag] || 0)}"
      f.puts "Peak magnitude: #{format('%.8f', interp[:peak_mag] || 0)}"
      f.puts "Right neighbor magnitude: #{format('%.8f', interp[:right_mag] || 0)}"
      f.puts "Interpolated frequency: #{format('%.4f', interp[:interpolated_freq] || 0)} Hz"
      f.puts "Integer-bin frequency: #{format('%.4f', interp[:peak_bin_freq] || 0)} Hz"
      correction = (interp[:interpolated_freq] || 0) - (interp[:peak_bin_freq] || 0)
      f.puts "Correction: #{format('%.4f', correction)} Hz"
    end

    File.write('/app/output/manifest.txt', "#{sensor_id}_analysis.json\n#{sensor_id}_spectrum.csv\ninterpolation_report.txt\n")
  end
end
RUBY

cd /app && ruby -e "
require '/app/lib/spectral_analyzer'
sa = SpectralAnalyzer.new
sa.run!
puts 'Analysis with interpolation complete'
"
