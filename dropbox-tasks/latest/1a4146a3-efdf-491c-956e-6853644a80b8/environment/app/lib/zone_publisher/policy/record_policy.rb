# frozen_string_literal: true

require "zone_publisher/dns/txt"
require "zone_publisher/report/evidence"
require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module RecordPolicy
      module_function

      def evaluate(zone, records)
        findings = []
        records.each do |rr|
          unless rr.ttl.between?(30, 86_400)
            findings << Report::Finding.new(
              zone: zone, owner: rr.owner, record_type: rr.type, code: "TTL_OUT_OF_RANGE",
              severity: "blocking", evidence: Report::Evidence.for_code("TTL_OUT_OF_RANGE")
            )
          end
          next unless rr.type == "TXT"
          next if Dns::Txt.canonical?(rr.rdata)

          findings << Report::Finding.new(
            zone: zone, owner: rr.owner, record_type: "TXT", code: "TXT_CANONICAL",
            severity: "blocking", evidence: Report::Evidence.for_code("TXT_CANONICAL")
          )
        end
        findings
      end
    end
  end
end
