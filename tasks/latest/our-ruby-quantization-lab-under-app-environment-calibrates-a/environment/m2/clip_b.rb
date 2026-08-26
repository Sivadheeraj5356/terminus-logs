# frozen_string_literal: true

require_relative 'stub_clip'

module M2
  module ClipB
    module_function

    def clip_b(tensor_vals, bound_table, layer_ctx)
      lo = bound_table.fetch('lo', -1.0)
      hi = bound_table.fetch('hi', 1.0)
      M2::StubClip.round_then_clip(tensor_vals, lo, hi)
    end
  end
end
