# frozen_string_literal: true

require "json"
require "zone_publisher/cli/errors"
require "zone_publisher/records/rr"
require "zone_publisher/records/validate"
require "zone_publisher/dns/name"

module ZonePublisher
  module Records
    module Journal
      module_function

      def load(path)
        rows = []
        File.foreach(path, chomp: true).with_index(1) do |line, idx|
          stripped = line.strip
          next if stripped.empty?

          begin
            obj = JSON.parse(stripped)
          rescue JSON::ParserError
            raise Cli::FatalError, "malformed NDJSON journal record on line #{idx}"
          end
          raise Cli::FatalError, "malformed NDJSON journal record on line #{idx}" unless obj.is_a?(Hash)

          required = %w[change_id seq action zone owner ttl record_type rdata effective_utc correction_of reason]
          required.each do |k|
            raise Cli::FatalError, "missing journal field #{k}" unless obj.key?(k)
          end
          action = Validate.action!(obj["action"])
          type = Validate.type!(obj["record_type"], "journal")
          raise Cli::FatalError, "unknown record type #{obj["record_type"]}" if type == "*"

          Validate.owner!(obj["zone"], "journal zone")
          Validate.owner!(obj["owner"], "journal owner")
          ttl = Validate.ttl!(obj["ttl"], "journal", allow_zero: action == "delete")
          eff = Validate.utc!(obj["effective_utc"], "journal effective_utc")
          begin
            seq = Integer(obj["seq"])
          rescue ArgumentError, TypeError
            raise Cli::FatalError, "malformed journal seq"
          end
          rows << JournalChange.new(
            change_id: obj["change_id"].to_s,
            seq: seq,
            action: action,
            zone: Dns::Name.normalize(obj["zone"]),
            owner: Dns::Name.normalize(obj["owner"]),
            ttl: ttl,
            record_type: type,
            rdata: obj["rdata"].to_s,
            effective_utc: eff,
            correction_of: obj["correction_of"].to_s,
            reason: obj["reason"].to_s
          )
        end
        resolve(rows)
      end

      def resolve(rows)
        by_id = {}
        rows.each do |r|
          by_id[r.change_id] = r
        end
        # Apply corrections in file/row arrival order without seq comparison.
        ordered = rows
        ordered.each do |r|
          next if r.correction_of.empty?

          target = by_id[r.correction_of]
          next unless target

          repl = r.dup
          repl.change_id = target.change_id
          repl.correction_of = ""
          by_id[target.change_id] = repl
          by_id.delete(r.change_id) if r.change_id != target.change_id
        end
        by_id.values
      end
    end
  end
end
