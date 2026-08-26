# frozen_string_literal: true
require "json"
require "digest"

module EvalCore
  module_function

  def parse_simple_toml(path)
    data = {}
    section = nil
    File.readlines(path, chomp: true).each do |line|
      line = line.strip
      next if line.empty? || line.start_with?("#")
      if line =~ /^\[([^\]]+)\]$/
        section = $1
        data[section] ||= {}
        next
      end
      if line =~ /^([A-Za-z0-9_]+)\s*=\s*(.+)$/
        key = $1
        raw = $2.strip
        val = if raw.start_with?("[")
                raw.gsub(/[\[\]\"]/, "").split(",").map(&:strip).reject(&:empty?)
              elsif raw =~ /^\d+$/
                raw.to_i
              else
                raw.gsub(/\A"|"\z/, "")
              end
        if section
          data[section][key] = val
        else
          data[key] = val
        end
      end
    end
    data
  end

  def load_profile(path)
    h = parse_simple_toml(path)
    {
      "id" => h["id"] || File.basename(path, ".toml"),
      "epoch" => h["epoch"].to_s,
      "tol_prefix" => (h["tol_prefix"] || 64).to_i,
      "band" => h["band"].to_s
    }
  end

  def load_pins(path)
    parse_simple_toml(path)
  end

  def build_ledger(pins, epoch)
    by = {}
    pins.each do |ek, vals|
      next unless vals.is_a?(Hash)
      by[ek] = {
        "allow" => Array(vals["allow"]).map(&:to_s),
        "rev" => Array(vals["rev"]).map(&:to_s)
      }
    end
    cur = by["e_hi"] || {"allow" => [], "rev" => []}
    {
      "e_tag" => epoch.to_s,
      "cur" => cur,
      "by_epoch" => by,
      "allow" => (by[epoch.to_s] || {})["allow"] || [],
      "rev" => (by[epoch.to_s] || {})["rev"] || []
    }
  end

  def canonical_bytes(rows)
    accepted = rows.select { |r| r["plan"] == "ok" && r["gate"] == "pass" }
    accepted = accepted.sort_by { |r| r["tid"].to_s }
    compact = accepted.map do |r|
      {
        "tid" => r["tid"].to_s,
        "kid" => r["kid"].to_s,
        "plan" => r["plan"].to_s,
        "gate" => r["gate"].to_s,
        "e_tag" => r["e_tag"].to_s
      }
    end
    JSON.generate(compact)
  end

  def digest_hex(bytes)
    Digest::SHA256.hexdigest(bytes)
  end

  def cfg_fp(keys)
    Digest::SHA256.hexdigest(Array(keys).map(&:to_s).sort.join(","))
  end

  def tol_ok(got, want, tol_prefix, slice_mode)
    need = slice_mode.to_s == "full" ? 64 : tol_prefix.to_i
    need = 64 if need > 64
    need = 1 if need < 1
    got.to_s[0, need] == want.to_s[0, need]
  end

  def inferred_spec_doc
    {
      "schema" => "k84-spec-v1",
      "clauses" => [
        {"aid" => "A1", "kind" => "cfg_iso", "note" => "effective cfg keys omit overlay pollution markers"},
        {"aid" => "A2", "kind" => "w_bind", "note" => "accepted witness rows bind the active profile epoch tag"},
        {"aid" => "A3", "kind" => "rev_iso", "note" => "gate acceptance follows per-epoch journal bands"}
      ],
      "band_epoch" => {"pri_hi" => "e_hi", "pri_lo" => "e_lo"}
    }
  end
end
