# frozen_string_literal: true

module ZonePublisher
  module Report
    module Sort
      module_function

      def findings(list)
        list.sort_by(&:owner)
      end

      def suppressed(list)
        list.sort_by(&:owner)
      end
    end
  end
end
