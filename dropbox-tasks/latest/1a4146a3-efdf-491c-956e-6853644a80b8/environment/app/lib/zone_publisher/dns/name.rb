# frozen_string_literal: true

module ZonePublisher
  module Dns
    module Name
      module_function

      def absolute?(name)
        name.is_a?(String) && !name.empty? && name.end_with?(".")
      end

      def normalize(name)
        name.to_s.downcase
      end

      def equal?(a, b)
        normalize(a) == normalize(b)
      end

      def matches_suffix?(name, suffix)
        n = normalize(name)
        s = normalize(suffix)
        return true if n == s

        n.end_with?("." + s)
      end

      def descendant_of?(name, suffix)
        n = normalize(name)
        s = normalize(suffix)
        return false if n == s

        n.end_with?("." + s)
      end

      def inside_delegated_child?(ns_name, child_apex)
        matches_suffix?(ns_name, child_apex)
      end

      def wildcard?(name)
        normalize(name).start_with?("*.")
      end
    end
  end
end
