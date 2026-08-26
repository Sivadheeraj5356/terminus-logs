# frozen_string_literal: true

def fmt_overlay_keys(h)
  return [] unless h.is_a?(Hash)
  h.keys.map(&:to_s).sort
end
