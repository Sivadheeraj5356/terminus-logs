# frozen_string_literal: true

require "zone_publisher/dns/name"
require "zone_publisher/report/evidence"
require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module CnamePolicy
      module_function

      def evaluate(zone, records)
        findings = []
        by_owner = records.group_by { |rr| rr.owner.downcase }
        by_owner.each do |owner, rrs|
          types = rrs.map(&:type).uniq
          if Dns::Name.equal?(owner, zone) && types.include?("CNAME") && !types.include?("SOA")
            findings << Report::Finding.new(
              zone: zone, owner: owner, record_type: "CNAME", code: "APEX_CNAME",
              severity: "blocking", evidence: Report::Evidence.for_code("APEX_CNAME")
            )
          end
          next unless types.include?("CNAME")

          others = types - ["CNAME"]
          conflict = others - %w[MX TXT CAA RRSIG NSEC SOA NS]
          next if conflict.empty?

          findings << Report::Finding.new(
            zone: zone, owner: owner, record_type: "CNAME", code: "CNAME_CONFLICT",
            severity: "blocking", evidence: Report::Evidence.for_code("CNAME_CONFLICT")
          )
        end
        findings
      end
    end
  end
end
