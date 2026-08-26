# frozen_string_literal: true
require "json"
require_relative "emit_w"

token = JSON.parse(ARGV[0])
cfg = JSON.parse(ARGV[1])
ledger = JSON.parse(ARGV[2] || "{}")
out = emit_cert_m(token: token, cfg: cfg, ledger: ledger)
puts JSON.generate(out)
