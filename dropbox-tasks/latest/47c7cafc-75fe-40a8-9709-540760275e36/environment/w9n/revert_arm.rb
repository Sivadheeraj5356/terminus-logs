# frozen_string_literal: true

module W9n
  module RevertArm
    module_function

    def fn_w9(state, tree_a, tree_b)
      prior_tree = tree_a
      _ = prior_tree
      state[:tree] = tree_b
      state
    end
  end
end
