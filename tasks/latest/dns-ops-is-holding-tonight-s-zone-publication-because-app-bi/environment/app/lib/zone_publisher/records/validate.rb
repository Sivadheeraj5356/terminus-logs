# frozen_string_literal: true

require "time"
require "zone_publisher/cli/errors"
require "zone_publisher/dns/name"
require "zone_publisher/records/rr"

module ZonePublisher
  module Records
    module Validate
      module_function

      def utc!(value, label)
        s = value.to_s
        raise Cli::FatalError, "invalid timestamp for #{label}" unless s.end_with?("Z")

        Time.iso8601(s)
      rescue ArgumentError
        raise Cli::FatalError, "invalid timestamp for #{label}"
      end

      def owner!(name, label)
        raise Cli::FatalError, "malformed owner name for #{label}" unless Dns::Name.absolute?(name)
      end

      def type!(type, label)
        t = type.to_s.upcase
        raise Cli::FatalError, "unknown record type #{type}" unless SUPPORTED_TYPES.include?(t) || t == "*"

        t
      end

      def action!(action)
        a = action.to_s
        raise Cli::FatalError, "unknown action #{action}" unless ACTIONS.include?(a)

        a
      end

      def finding_code!(code)
        c = code.to_s
        raise Cli::FatalError, "unknown finding code #{code}" unless FINDING_CODES.include?(c)

        c
      end

      def ttl!(value, label, allow_zero: false)
        begin
          n = Integer(value)
        rescue ArgumentError, TypeError
          raise Cli::FatalError, "malformed TTL for #{label}"
        end
        return n if allow_zero && n.zero?
        raise Cli::FatalError, "malformed TTL for #{label}" unless n.between?(30, 86_400)

        n
      end
    end
  end
end
