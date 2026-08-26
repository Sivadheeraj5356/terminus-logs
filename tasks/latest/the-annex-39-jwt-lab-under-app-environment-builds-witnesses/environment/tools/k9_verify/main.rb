# frozen_string_literal: true
require "json"
require "fileutils"
require "open3"
require_relative "eval_core"
require_relative "../../r43/rot_fold"

ENV_ROOT = "/app/environment"
RB = ENV_ROOT

def die(msg, code=2)
  warn msg
  exit code
end

def parse_args(argv)
  opts = {"matrix" => "all", "witness_out" => "/app/output/replay_witness.json", "spec_out" => "/app/output/inferred_spec.json"}
  i = 0
  while i < argv.length
    case argv[i]
    when "--matrix" then opts["matrix"] = argv[i+1]; i += 2
    when "--witness-out" then opts["witness_out"] = argv[i+1]; i += 2
    when "--spec-out" then opts["spec_out"] = argv[i+1]; i += 2
    else
      die("unknown arg #{argv[i]}")
    end
  end
  opts
end

def ruby_run(script, *args)
  out, err, st = Open3.capture3("ruby", script, *args)
  die("driver failed: #{script}: #{err}") unless st.success?
  out
end

def run_cell(grid_name, profile)
  sc = JSON.parse(File.read(File.join(ENV_ROOT, "scenarios", "#{grid_name}.json")))
  epoch = profile["epoch"]
  ledger = RotFold.ledger_for(epoch)

  cfg_json = ruby_run(
    File.join(RB, "r41/run_q.rb"),
    JSON.generate(sc["base_cfg"]),
    JSON.generate(sc["overlay"]),
    JSON.generate({"grid" => grid_name})
  )
  cfg = JSON.parse(cfg_json)
  eff_keys = cfg.keys.map(&:to_s).sort
  fp = EvalCore.cfg_fp(eff_keys)

  rows = []
  sc["tokens"].each do |tok|
    cert = JSON.parse(ruby_run(
      File.join(RB, "r42/run_m.rb"),
      JSON.generate(tok),
      JSON.generate(cfg),
      JSON.generate(ledger)
    ))
    gate_raw = ruby_run(
      File.join(RB, "r43/run_k.rb"),
      JSON.generate(tok),
      JSON.generate(ledger),
      epoch
    ).strip
    gate = gate_raw == "1" ? "pass" : "hold"
    rows << {
      "tid" => tok["id"].to_s,
      "kid" => cert["kid"].to_s,
      "plan" => cert["plan"].to_s,
      "gate" => gate,
      "e_tag" => cert["e_tag"].to_s
    }
  end

  meta_state = "aligned"
  remap = sc["meta_remap"] || {}
  remap.each do |src, dst|
    src_row = rows.find { |r| r["tid"] == src }
    next unless src_row
    tok = sc["tokens"].find { |t| t["id"] == src }.dup
    tok["id"] = dst
    cert = JSON.parse(ruby_run(
      File.join(RB, "r42/run_m.rb"),
      JSON.generate(tok),
      JSON.generate(cfg),
      JSON.generate(ledger)
    ))
    gate_raw = ruby_run(
      File.join(RB, "r43/run_k.rb"),
      JSON.generate(tok),
      JSON.generate(ledger),
      epoch
    ).strip
    gate = gate_raw == "1" ? "pass" : "hold"
    if cert["plan"].to_s != src_row["plan"] || gate != src_row["gate"] || cert["kid"].to_s != src_row["kid"] || cert["e_tag"].to_s != src_row["e_tag"]
      meta_state = "diverged"
    end
  end

  bytes = EvalCore.canonical_bytes(rows)
  digest = EvalCore.digest_hex(bytes)
  {
    "grid" => grid_name,
    "profile" => profile["id"],
    "rows" => rows,
    "meta_state" => meta_state,
    "instance_digest" => digest,
    "eff_keys" => eff_keys,
    "cfg_fp" => fp,
    "_tol" => profile["tol_prefix"],
    "_slice_mode" => sc["slice_mode"].to_s,
    "_epoch" => epoch
  }
end

def cell_ok?(cell, prof)
  return false unless cell["meta_state"] == "aligned"
  return false if cell["eff_keys"].include?("__p") || cell["eff_keys"].include?("x_def")
  return false unless cell["cfg_fp"] == EvalCore.cfg_fp(cell["eff_keys"])

  ok_rows = cell["rows"].select { |r| r["plan"] == "ok" }
  return false if ok_rows.empty?
  return false unless ok_rows.all? { |r| r["e_tag"] == prof["epoch"] }
  return false if cell["rows"].any? { |r| r["kid"].to_s.start_with?("k_evil") }
  return false if cell["rows"].any? { |r| r["kid"] == "k_root" }

  accepted = cell["rows"].count { |r| r["plan"] == "ok" && r["gate"] == "pass" }
  return false if accepted < 1

  true
end

opts = parse_args(ARGV)
grids = %w[pocket ridge slate marsh]
profiles = %w[pri_hi pri_lo].map do |pid|
  EvalCore.load_profile(File.join(ENV_ROOT, "pri", "#{pid}.toml"))
end

FileUtils.mkdir_p(File.dirname(opts["witness_out"]))
FileUtils.mkdir_p(File.dirname(opts["spec_out"]))
FileUtils.mkdir_p("/app/output/stage")
FileUtils.mkdir_p("/app/output/traces")

out = {"grids" => {}}
failures = []

grids.each do |g|
  out["grids"][g] = {}
  profiles.each do |prof|
    cell = run_cell(g, prof)
    ok = cell_ok?(cell, prof)
    failures << "#{g}/#{prof['id']}" unless ok
    pub = cell.reject { |k, _| k.start_with?("_") }
    out["grids"][g][prof["id"]] = pub
  end
end

File.write("/app/output/stage/hud.json", JSON.pretty_generate({
  "hud_only" => true,
  "tallies" => grids.map { |g| [g, out["grids"][g].values.map { |c| c["rows"].size }.sum] }.to_h
}))

File.write(opts["witness_out"], JSON.pretty_generate(out))

if failures.empty?
  File.write(opts["spec_out"], JSON.pretty_generate(EvalCore.inferred_spec_doc))
  exit 0
else
  File.write(opts["spec_out"], JSON.pretty_generate({
    "schema" => "k84-spec-v1",
    "clauses" => [],
    "band_epoch" => {},
    "pending" => failures
  }))
  warn "matrix failures: #{failures.join(',')}"
  exit 1
end
