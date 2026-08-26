# frozen_string_literal: true

module Q9
  module ShadowArm
    @global_pool = { min: Float::INFINITY, max: -Float::INFINITY }

    module_function

    def touch(vals)
      vals.each do |v|
        f = v.to_f
        @global_pool[:min] = f if f < @global_pool[:min]
        @global_pool[:max] = f if f > @global_pool[:max]
      end
      @global_pool.dup
    end

    def reset!
      @global_pool = { min: Float::INFINITY, max: -Float::INFINITY }
    end
  end
end
