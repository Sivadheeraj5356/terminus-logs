# frozen_string_literal: true

require_relative 'shadow_arm'

module Q9
  module ArmA
    module_function

    def arm_a(row_set, mode_map)
      vals = row_set.flat_map { |row| Array(row['vals']) }
      Q9::ShadowArm.touch(vals)
    end
  end
end
