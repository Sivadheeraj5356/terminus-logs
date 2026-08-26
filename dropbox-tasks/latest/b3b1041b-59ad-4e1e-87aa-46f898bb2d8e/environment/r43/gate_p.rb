# frozen_string_literal: true

def _cur_band(ledger)
  ledger.is_a?(Hash) ? (ledger["cur"] || {}) : {}
end

def _kid_of(token)
  token.is_a?(Hash) ? token["kid"].to_s : ""
end

def ensure_rev_k(token:, ledger:, epoch:)
  kid = _kid_of(token)
  cur = _cur_band(ledger)
  allow = (cur["allow"] || []).map(&:to_s)
  rev = (cur["rev"] || []).map(&:to_s)
  return false if rev.include?(kid)
  allow.include?(kid)
end
