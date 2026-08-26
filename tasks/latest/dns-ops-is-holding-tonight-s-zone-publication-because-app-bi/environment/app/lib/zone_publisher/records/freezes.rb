# frozen_string_literal: true

require "csv"
require "zone_publisher/cli/errors"
require "zone_publisher/records/rr"
require "zone_publisher/records/validate"
require "zone_publisher/dns/name"

module ZonePublisher
  module Records
    module Freezes
      HEADER = %w[freeze_id zone owner_suffix record_type start_utc end_utc reason].freeze

      module_function

      def load(path)
        rows = []
        raw = File.read(path)
        table = CSV.parse(raw, headers: true)
        raise Cli::FatalError, "freeze CSV headers must be exact and ordered" if table.headers.nil?
        raise Cli::FatalError, "freeze CSV headers must be exact and ordered" unless table.headers == HEADER

        table.each_with_index do |row, idx|
          HEADER.each do |h|
            raise Cli::FatalError, "missing freeze field #{h}" if row[h].nil?
          end
          Validate.owner!(row["zone"], "freeze zone")
          Validate.owner!(row["owner_suffix"], "freeze owner_suffix")
          type = Validate.type!(row["record_type"], "freeze")
          start_t = Validate.utc!(row["start_utc"], "freeze start_utc")
          end_t = Validate.utc!(row["end_utc"], "freeze end_utc")
          rows << FreezeRow.new(
            freeze_id: row["freeze_id"],
            zone: Dns::Name.normalize(row["zone"]),
            owner_suffix: Dns::Name.normalize(row["owner_suffix"]),
            record_type: type,
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
