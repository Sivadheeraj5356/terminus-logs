#!/usr/bin/env ruby
# frozen_string_literal: true

require "json"
require "bigdecimal"
require "bigdecimal/util"

PREC = 60
MAGIC = "CFR1"

def d(x)
  BigDecimal(x.to_s)
end

def round3(x)
  d(x).round(3, BigDecimal::ROUND_HALF_EVEN)
end

def subdivisions(k, dt)
  n = (d(k).div(d(dt), PREC)).round(0, BigDecimal::ROUND_HALF_EVEN).to_i
  n < 1 ? 1 : n
end

def coeffs(k, x, dt)
  half = d(dt) * d("0.5")
  denom = k * (BigDecimal("1") - x) + half
  c0 = (half - k * x).div(denom, PREC)
  c1 = (half + k * x).div(denom, PREC)
  c2 = (k * (BigDecimal("1") - x) - half).div(denom, PREC)
  [c0, c1, c2]
end

def route_once(inflow, k, x, dt)
  c0, c1, c2 = coeffs(k, x, dt)
  n = inflow.length
  out = Array.new(n) { BigDecimal("0") }
  out[0] = round3(inflow[0])
  (1...n).each do |t|
    raw = c0 * inflow[t] + c1 * inflow[t - 1] + c2 * out[t - 1]
    out[t] = round3(raw)
  end
  out
end

def route_reach(inflow, k, x, dt)
  n = subdivisions(k, dt)
  ksub = d(k).div(d(n), PREC)
  series = inflow
  n.times { series = route_once(series, ksub, d(x), dt) }
  series
end

# Little-endian binary field survey reader.
class Survey
  def initialize(bytes)
    @io = bytes
    @pos = 0
  end

  def take(len)
    raise "truncated survey" if @pos + len > @io.bytesize
    slice = @io.byteslice(@pos, len)
    @pos += len
    slice
  end

  def u8
    take(1).unpack1("C")
  end

  def u16
    take(2).unpack1("v")
  end

  def f64
    take(8).unpack1("E")
  end

  def name
    take(u8)
  end

  def parse
    raise "bad magic" unless take(4) == MAGIC
    dt = f64
    peak = f64
    reaches = []
    u16.times do
      rid = name
      river_km = f64
      k = f64
      x = f64
      ups = Array.new(u8) { name }
      reaches << { "reach_id" => rid, "river_km" => river_km, "K" => k, "X" => x, "upstream" => ups }
    end
    events = []
    u16.times do
      ev_name = name
      steps = u16
      headwater = Array.new(steps) { f64 }
      laterals = {}
      u8.times do
        lid = name
        laterals[lid] = Array.new(steps) { f64 }
      end
      events << { "name" => ev_name, "headwater" => headwater, "laterals" => laterals }
    end
    { "dt_hours" => dt, "peak_min_cms" => peak, "reaches" => reaches, "events" => events }
  end
end

def lateral_series(laterals, rid, n)
  raw = laterals[rid]
  return Array.new(n) { BigDecimal("0") } unless raw
  out = Array.new(n) { BigDecimal("0") }
  (0...n).each do |t|
    prev = t.zero? ? BigDecimal("0") : d(raw[t - 1])
    out[t] = round3((d(raw[t]) + prev).div(d(2), PREC))
  end
  out
end

def process_order(reaches)
  by_id = {}
  reaches.each { |r| by_id[r["reach_id"]] = r }
  done = {}
  order = []
  loop do
    ready = reaches.reject { |r| done[r["reach_id"]] }
                   .select { |r| (r["upstream"] || []).all? { |u| done[u] || !by_id.key?(u) } }
    break if ready.empty?
    ready.sort_by { |r| r["reach_id"] }.each do |r|
      order << r
      done[r["reach_id"]] = true
    end
  end
  order
end

def analyze(survey, event)
  dt = survey["dt_hours"]
  peak_min = d(survey["peak_min_cms"])
  headwater = event["headwater"].map { |v| d(v) }
  laterals = event["laterals"] || {}
  n = headwater.length

  admitted = {}
  process_order(survey["reaches"]).each do |r|
    rid = r["reach_id"]
    ups = r["upstream"] || []
    base =
      if ups.empty?
        headwater.dup
      else
        arr = Array.new(n) { BigDecimal("0") }
        (1...n).each do |t|
          ups.each do |u|
            up = admitted[u]
            arr[t] += up[t - 1] if up
          end
        end
        arr
      end
    lat = lateral_series(laterals, rid, n)
    i_eff = Array.new(n) { |t| base[t] + lat[t] }
    series = route_reach(i_eff, r["K"], r["X"], dt)
    peak = series.max
    admitted[rid] = series if peak >= peak_min
  end

  hydrographs = []
  survey["reaches"].sort_by { |r| r["reach_id"] }.each do |r|
    rid = r["reach_id"]
    series = admitted[rid]
    next unless series
    peak = series.max
    ttp = round3(series.index(peak) * d(dt))
    hydrographs << {
      "reach_id" => rid,
      "peak_cms" => peak.to_f,
      "time_to_peak_h" => ttp.to_f,
      "outflow_cms" => series.map(&:to_f)
    }
  end
  hydrographs
end

survey_path = ARGV[0]
abort "usage: channel-route SURVEY.bin" unless survey_path
survey = Survey.new(File.binread(survey_path)).parse
result = {}
survey["events"].each do |ev|
  result[ev["name"]] = analyze(survey, ev)
end
puts JSON.pretty_generate(result)
