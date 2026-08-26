# frozen_string_literal: true

require "csv"
require "zone_publisher/cli/errors"
require "zone_publisher/records/rr"
require "zone_publisher/records/validate"
require "zone_publisher/dns/name"

module ZonePublisher
  module Records
    module Exceptions
      HEADER = %w[exception_id zone owner_suffix record_type code start_utc end_utc reason].freeze

      module_function

      def load(path)
        rows = []
        raw = File.read(path)
        table = CSV.parse(raw, headers: true)
        raise Cli::FatalError, "exception CSV headers must be exact and ordered" if table.headers.nil?
        raise Cli::FatalError, "exception CSV headers must be exact and ordered" unless table.headers == HEADER

        table.each do |row|
          HEADER.each do |h|
            raise Cli::FatalError, "missing exception field #{h}" if row[h].nil?
          end
          Validate.owner!(row["zone"], "exception zone")
          Validate.owner!(row["owner_suffix"], "exception owner_suffix")
          type = Validate.type!(row["record_type"], "exception")
          code = Validate.finding_code!(row["code"])
          start_t = Validate.utc!(row["start_utc"], "exception start_utc")
          end_t = Validate.utc!(row["end_utc"], "exception end_utc")
          rows << ExceptionRow.new(
            exception_id: row["exception_id"],
            zone: Dns::Name.normalize(row["zone"]),
            owner_suffix: Dns::Name.normalize(row["owner_suffix"]),
            record_type: type,
            code: code,
            start_utc: start_t,
            end_utc: end_t,
            reason: row["reason"]
          )
        end
        rows
      end
    end
  end
end
