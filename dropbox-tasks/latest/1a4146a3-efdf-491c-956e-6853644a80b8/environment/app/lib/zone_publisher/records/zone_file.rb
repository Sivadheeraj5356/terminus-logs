# frozen_string_literal: true

require "zone_publisher/cli/errors"
require "zone_publisher/records/rr"
require "zone_publisher/records/validate"
require "zone_publisher/dns/name"

module ZonePublisher
  module Records
    module ZoneFile
      module_function

      def load(path)
        rows = []
        File.foreach(path, chomp: true).with_index(1) do |line, idx|
          stripped = line.strip
          next if stripped.empty? || stripped.start_with?(";")

          parts = stripped.split(/\s+/, 5)
          raise Cli::FatalError, "malformed zone RR on line #{idx}" if parts.length < 5

          owner, ttl_s, klass, type, rdata = parts
          Validate.owner!(owner, "zone line #{idx}")
          ttl = begin
            Integer(ttl_s)
          rescue ArgumentError
            raise Cli::FatalError, "malformed TTL for zone line #{idx}"
          end
          raise Cli::FatalError, "TTL out of parse range on zone line #{idx}" unless ttl.between?(30, 86_400)
          raise Cli::FatalError, "class must be IN on zone line #{idx}" unless klass == "IN"

          type_u = Validate.type!(type, "zone line #{idx}")
          raise Cli::FatalError, "unknown record type #{type}" if type_u == "*"

          rows << RR.new(owner: Dns::Name.normalize(owner), ttl: ttl, klass: "IN", type: type_u, rdata: rdata.strip)
        end
        rows
      end
    end
  end
end
