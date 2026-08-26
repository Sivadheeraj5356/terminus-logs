# frozen_string_literal: true

def _pick_kid(token)
  token.is_a?(Hash) ? token["kid"].to_s : ""
end

def _allow_for(ledger, e_tag)
  allow = []
  if ledger.is_a?(Hash)
    allow = Array(ledger["allow"]).map(&:to_s)
    if allow.empty? && ledger["by_epoch"].is_a?(Hash)
      band = ledger["by_epoch"][e_tag.to_s] || {}
      allow = Array(band["allow"]).map(&:to_s)
    end
  end
  allow
end

def _plan_for(kid, allow)
  allow.include?(kid) ? "ok" : "skip"
end

def emit_cert_m(token:, cfg:, ledger:)
  tid = token.is_a?(Hash) ? token["id"].to_s : ""
  kid = _pick_kid(token)
  e_tag = ledger.is_a?(Hash) ? ledger["e_tag"].to_s : ""
  allow = _allow_for(ledger, e_tag)
  plan = _plan_for(kid, allow)
  {
    "t" => tid,
    "kid" => kid,
    "plan" => plan,
    "e_tag" => e_tag
  }
end
