# frozen_string_literal: true

def _cur_band(ledger)
  ledger.is_a?(Hash) ? (ledger["cur"] || {}) : {}
end

def _kid_of(token)
  token.is_a?(Hash) ? token["kid"].to_s : ""
end

def _band_for(ledger, epoch)
  return {} unless ledger.is_a?(Hash) && ledger["by_epoch"].is_a?(Hash)
  ledger["by_epoch"][epoch.to_s] || {}
end

def _lists_for(band)
  allow = Array(band["allow"]).map(&:to_s)
  rev = Array(band["rev"]).map(&:to_s)
  [allow, rev]
end

def ensure_rev_k(token:, ledger:, epoch:)
  kid = _kid_of(token)
  band = _band_for(ledger, epoch)
  allow, rev = _lists_for(band)
  return false if rev.include?(kid)
  allow.include?(kid)
end
