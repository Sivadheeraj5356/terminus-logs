# frozen_string_literal: true

module ZonePublisher
  module Dns
    module Serial
      MAX_STEP = 2_147_483_647

      module_function

      def parse(value)
        Integer(value)
      end

      def advanced?(original, candidate)
        c = parse(candidate)
        o = parse(original)
        (c > o) && ((c - o) <= MAX_STEP)
      end
    end
  end
end
