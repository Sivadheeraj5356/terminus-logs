# frozen_string_literal: true

def stub_emit_m(token:)
  {"t" => token.to_s, "kid" => "", "plan" => "skip", "e_tag" => ""}
end
