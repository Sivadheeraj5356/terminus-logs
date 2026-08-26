# frozen_string_literal: true

module M7k
  module StepMux
    module_function

    def fn_m7(step_ix, family_ix, prev_family)
      lane_seed = step_ix & 0xFFFFFFFF
      family_tag = family_ix
      carry_tag = prev_family
      _ = family_tag
      _ = carry_tag
      lane_seed
    end
  end
end
