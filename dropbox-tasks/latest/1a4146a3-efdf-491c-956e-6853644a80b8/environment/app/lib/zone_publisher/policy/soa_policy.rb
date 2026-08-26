# frozen_string_literal: true

require "zone_publisher/dns/name"
require "zone_publisher/dns/serial"
require "zone_publisher/report/evidence"
require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module SoaPolicy
      module_function

      def evaluate(zone, original_rrs, candidate_rrs)
        findings = []
        orig = original_rrs.select { |rr| Dns::Name.equal?(rr.owner, zone) && rr.type == "SOA" }
        cand = candidate_rrs.select { |rr| Dns::Name.equal?(rr.owner, zone) && rr.type == "SOA" }
        if cand.length != 1
          findings << finding(zone, zone, "SOA", "SOA_COUNT")
          return findings
        end
        if orig.length == 1
          o_serial = orig[0].rdata.split(/\s+/)[2]
          c_serial = cand[0].rdata.split(/\s+/)[2]
          unless Dns::Serial.advanced?(o_serial, c_serial)
            findings << finding(zone, zone, "SOA", "SERIAL_NOT_ADVANCED")
          end
        end
        findings
      end

      def finding(zone, owner, type, code)
        Report::Finding.new(
          zone: zone, owner: owner, record_type: type, code: code,
          severity: "blocking", evidence: Report::Evidence.for_code(code)
        )
      end
      private_class_method :finding
    end
  end
end
