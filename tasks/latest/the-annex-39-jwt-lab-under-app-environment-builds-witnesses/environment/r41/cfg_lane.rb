# frozen_string_literal: true

def _dup_h(h)
  return h unless h.is_a?(Hash)
  out = {}
  h.each { |k, v| out[k] = v.is_a?(Hash) ? _dup_h(v) : v }
  out
end

def _overlay_keys(overlay)
  return [] unless overlay.is_a?(Hash)
  overlay.keys.map(&:to_s).sort
end

def _root_q_snapshot(base)
  return {} unless base.is_a?(Hash) && base["root_q"].is_a?(Hash)
  _dup_h(base["root_q"])
end

def bind_merge_q(base:, overlay:, ctx:)
  out = _dup_h(base)
  return out unless overlay.is_a?(Hash)
  overlay.each do |k, v|
    if out[k].is_a?(Hash) && v.is_a?(Hash)
      out[k] = bind_merge_q(base: out[k], overlay: v, ctx: ctx)
    else
      out[k] = v.is_a?(Hash) ? _dup_h(v) : v
    end
  end
  out
end
