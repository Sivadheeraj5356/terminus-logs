# frozen_string_literal: true

module Tools
  module GaugeMux
    module_function

    def early_tag(rows)
      return "steady" if rows.all? { |r| r[:bind_rc] == 1 }

      "split"
    end
  end
end
