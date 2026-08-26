# frozen_string_literal: true

module Tools
  module SummaryMux
    module_function

    def span_band(rows)
      rows.map { |r| r[:drift_code].abs }.max || 0
    end
  end
end
