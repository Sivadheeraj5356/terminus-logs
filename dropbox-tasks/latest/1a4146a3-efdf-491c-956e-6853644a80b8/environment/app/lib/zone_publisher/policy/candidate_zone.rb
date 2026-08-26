# frozen_string_literal: true

require "zone_publisher/records/rr"
require "zone_publisher/report/evidence"
require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module CandidateZone
      module_function

      Result = Struct.new(:records, :findings, :effective_times, keyword_init: true)

      def apply(zone_rrs, changes)
        records = zone_rrs.map(&:dup)
        findings = []
        effective_times = {}

        changes.sort_by(&:change_id).each do |ch|
          key_ot = [ch.owner, ch.record_type]
          effective_times[key_ot] = ch.effective_utc
          case ch.action
          when "add"
            records << Records::RR.new(owner: ch.owner, ttl: ch.ttl, klass: "IN", type: ch.record_type, rdata: ch.rdata)
          when "delete"
            before = records.length
            records.reject! { |rr| rr.owner == ch.owner && rr.type == ch.record_type && rr.rdata == ch.rdata }
            if records.length == before
              findings << Report::Finding.new(
                zone: ch.zone,
                owner: ch.owner,
                record_type: ch.record_type,
                code: "UNKNOWN_DELETE",
                severity: "blocking",
                evidence: Report::Evidence.for_code("UNKNOWN_DELETE")
              )
            end
          when "replace"
            records.reject! { |rr| rr.owner == ch.owner && rr.type == ch.record_type }
            records << Records::RR.new(owner: ch.owner, ttl: ch.ttl, klass: "IN", type: ch.record_type, rdata: ch.rdata)
          end
        end
        Result.new(records: records, findings: findings, effective_times: effective_times)
      end
    end
  end
end
