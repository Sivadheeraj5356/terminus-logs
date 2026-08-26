# frozen_string_literal: true

require "json"

module ZonePublisher
  module Report
    module CanonicalJson
      module_function

      def dump(obj)
        text = JSON.pretty_generate(obj)
        text = text.gsub(/\[\s*\]/, "[]")
        text.end_with?("\n") ? text : (text + "\n")
      end
    end
  end
end
