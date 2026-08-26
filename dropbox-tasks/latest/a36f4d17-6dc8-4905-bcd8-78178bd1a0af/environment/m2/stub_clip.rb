# frozen_string_literal: true

module M2
  module StubClip
    module_function

    def round_then_clip(vals, lo, hi)
      vals.map { |v| [[v.round, hi].min, lo].max }
    end
  end
end
