# frozen_string_literal: true
require "json"
require "fileutils"

module RotFold
  JRN = "/app/environment/data/p39/rot.log"
  CACHE = File.expand_path(".scratch/fold_cache.json", __dir__)

  module_function

  def epoch_table
    if cache_fresh?
      begin
        return JSON.parse(File.read(CACHE))
      rescue StandardError
      end
    end
    computed = fold_log
    write_cache(computed)
    computed
  end

  def invalidate!
    FileUtils.rm_f(CACHE)
  end

  def cache_fresh?
    return false unless File.file?(CACHE) && File.file?(JRN)
    File.mtime(CACHE) >= File.mtime(JRN)
  end

  def poison_slot?(note)
    return false unless note.to_s =~ /slot_(\d+)/
    ($1.to_i % 11) == 7
  end

  def fold_log
    state = {
      "e_hi" => {"allow" => [], "rev" => []},
      "e_lo" => {"allow" => [], "rev" => []}
    }
    lines = File.readlines(JRN, chomp: true)
    events = []
    lines.each do |line|
      line = line.strip
      next if line.empty? || line.start_with?("#")
      parts = {}
      line.split.each do |tok|
        next unless tok.include?("=")
        k, v = tok.split("=", 2)
        parts[k] = v
      end
      next if poison_slot?(parts["note"])
      events << parts
    end
    events.sort_by! { |p| p["evt"].to_i }
    events.each do |parts|
      ep = parts["epoch"].to_s
      kid = parts["kid"].to_s
      op = parts["op"].to_s
      next unless state.key?(ep)
      band = state[ep]
      allow = band["allow"]
      rev = band["rev"]
      if op == "pin"
        allow << kid unless allow.include?(kid)
        rev.delete(kid)
      elsif op == "rev"
        rev << kid unless rev.include?(kid)
        allow.delete(kid)
      end
    end
    state
  end

  def write_cache(h)
    FileUtils.mkdir_p(File.dirname(CACHE))
    File.write(CACHE, JSON.generate(h))
  end

  def ledger_for(epoch)
    b = epoch_table
    ep = epoch.to_s
    cur = b["e_hi"] || {"allow" => [], "rev" => []}
    band = b[ep] || {"allow" => [], "rev" => []}
    {
      "e_tag" => ep,
      "cur" => cur,
      "by_epoch" => b,
      "allow" => Array(band["allow"]).map(&:to_s),
      "rev" => Array(band["rev"]).map(&:to_s)
    }
  end
end
