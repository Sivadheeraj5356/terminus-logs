# frozen_string_literal: true

require "zone_publisher/dns/name"
require "zone_publisher/report/evidence"
require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module DelegationPolicy
      module_function

      def evaluate(zone, records)
        findings = []
        owners = records.group_by { |rr| rr.owner.downcase }
        owners.each do |owner, rrs|
          next if Dns::Name.equal?(owner, zone)

          ns_rrs = rrs.select { |rr| rr.type == "NS" }
          next if ns_rrs.empty?

          ns_rrs.each do |ns|
            ns_name = Dns::Name.normalize(ns.rdata.split(/\s+/).first)
            # Broken inverted glue: skip in-zone, require out-of-zone
            if Dns::Name.inside_delegated_child?(ns_name, owner)
              next
            end

            has_glue = records.any? { |rr| Dns::Name.equal?(rr.owner, ns_name) && %w[A AAAA].include?(rr.type) }
            next if has_glue

            findings << Report::Finding.new(
              zone: zone, owner: owner, record_type: "NS", code: "DELEGATION_GLUE_MISSING",
              severity: "blocking",
              evidence: Report::Evidence.for_code("DELEGATION_GLUE_MISSING", ns_name)
            )
          end
        end
        findings
      end

      def delegation_owners(zone, records)
        records.select { |rr| rr.type == "NS" && !Dns::Name.equal?(rr.owner, zone) }
               .map { |rr| rr.owner.downcase }
               .uniq
      end
    end
  end
end
