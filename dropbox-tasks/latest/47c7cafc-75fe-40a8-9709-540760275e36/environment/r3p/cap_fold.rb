# frozen_string_literal: true

module R3p
  module CapFold
    module_function

    def fn_r3(ctx, stamp_a, stamp_b)
      merged = (stamp_a ^ stamp_b) & 0xFFFFFFFF
      ctx[:published] = merged
      if ctx[:activated]
        merged
      else
        merged
      end
    end
  end
end
