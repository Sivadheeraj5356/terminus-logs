# frozen_string_literal: true

def _pick_kid(cfg, token)
  kid = ""
  if cfg.is_a?(Hash)
    if cfg.key?("x_def") && cfg["x_def"].is_a?(Hash) && cfg["x_def"]["kid"]
      kid = cfg["x_def"]["kid"].to_s
    elsif cfg.dig("root_q", "kid")
      kid = cfg.dig("root_q", "kid").to_s
    elsif cfg["kid"]
      kid = cfg["kid"].to_s
    end
  end
  kid = token["kid"].to_s if kid.empty? && token.is_a?(Hash)
  kid
end

def emit_cert_m(token:, cfg:, ledger:)
  tid = token.is_a?(Hash) ? token["id"].to_s : ""
  kid = _pick_kid(cfg, token)
  {
    "t" => tid,
    "kid" => kid,
    "plan" => "ok",
    "e_tag" => ""
  }
end
