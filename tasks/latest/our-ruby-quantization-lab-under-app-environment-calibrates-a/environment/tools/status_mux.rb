# frozen_string_literal: true

require 'json'

module Tools
  module StatusMux
    module_function

    def staging_summary(rows)
      totals = rows.group_by { |r| r['case_id'] }.transform_values(&:length)
      { 'headline' => totals }
    end
  end
end
