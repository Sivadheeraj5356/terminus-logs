#!/usr/bin/env ruby
# Sensor calibration utility — reads calibration logs and computes
# baseline offset and gain corrections.

require 'csv'

def load_calibration(path = '/app/data/calibration_log.csv')
  rows = CSV.read(path, headers: true)
  offsets = rows.map { |r| r['offset_mv'].to_f }
  gains = rows.map { |r| r['gain'].to_f }
  {
    mean_offset: offsets.sum / offsets.size,
    mean_gain: gains.sum / gains.size,
    samples: rows.size
  }
end

if __FILE__ == $0
  result = load_calibration
  puts "Mean offset: #{result[:mean_offset]} mV"
  puts "Mean gain:   #{result[:mean_gain]}"
  puts "Samples:     #{result[:samples]}"
end
