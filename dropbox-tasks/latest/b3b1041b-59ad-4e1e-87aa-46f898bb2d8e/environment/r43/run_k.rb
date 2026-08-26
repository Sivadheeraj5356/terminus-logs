# frozen_string_literal: true
require "json"
require_relative "gate_p"

token = JSON.parse(ARGV[0])
ledger = JSON.parse(ARGV[1])
epoch = ARGV[2].to_s
ok = ensure_rev_k(token: token, ledger: ledger, epoch: epoch)
puts(ok ? "1" : "0")
