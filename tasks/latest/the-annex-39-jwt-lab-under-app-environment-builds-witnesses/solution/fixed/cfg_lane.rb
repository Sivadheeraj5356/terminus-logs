# frozen_string_literal: true

def _dup_h(h)
  return h unless h.is_a?(Hash)
  out = {}
  h.each { |k, v| out[k] = v.is_a?(Hash) ? _dup_h(v) : v }
  out
end

def _overlay_skip?(key)
  ks = key.to_s
  ks.start_with?("__") || ks == "x_def"
end

def _overlay_keys(overlay)
  return [] unless overlay.is_a?(Hash)
  overlay.keys.map(&:to_s).sort
end

def _root_q_snapshot(base)
  return {} unless base.is_a?(Hash) && base["root_q"].is_a?(Hash)
  _dup_h(base["root_q"])
end

def _merge_overlay_field(out, key, value, ctx:)
  return out if _overlay_skip?(key)
  if out[key].is_a?(Hash) && value.is_a?(Hash)
    out[key] = bind_merge_q(base: out[key], overlay: value, ctx: ctx)
  else
    out[key] = value.is_a?(Hash) ? _dup_h(value) : value
  end
  out
end

def _sanitize_root_q(out, base, overlay)
  out["root_q"] = _root_q_snapshot(base)
  return out unless overlay.is_a?(Hash) && overlay["root_q"].is_a?(Hash)
  overlay["root_q"].each do |k, v|
    next if _overlay_skip?(k) || k.to_s == "kid"
    out["root_q"][k] = v
  end
  out
end

def bind_merge_q(base:, overlay:, ctx:)
  out = _dup_h(base)
  return out unless overlay.is_a?(Hash)
  overlay.each do |k, v|
    out = _merge_overlay_field(out, k, v, ctx: ctx)
  end
  _sanitize_root_q(out, base, overlay)
end
