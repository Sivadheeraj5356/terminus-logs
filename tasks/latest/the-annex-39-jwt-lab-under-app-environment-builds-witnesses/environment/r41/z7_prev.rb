# frozen_string_literal: true
# Offline benchmark helper; not invoked by matrix drivers.

def z7_shallow_q(base:, overlay:)
  out = {}
  base.each { |k, v| out[k] = v } if base.is_a?(Hash)
  overlay.each { |k, v| out[k] = v } if overlay.is_a?(Hash)
  out
end
