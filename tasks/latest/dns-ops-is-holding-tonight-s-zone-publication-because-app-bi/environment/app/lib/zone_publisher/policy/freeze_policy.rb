# frozen_string_literal: true

require "zone_publisher/report/evidence"
require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module FreezePolicy
      module_function

      def evaluate(changes, freezes)
        findings = []
        changes.each do |ch|
          freezes.each do |fz|
            type_ok = fz.record_type == "*" || fz.record_type == ch.record_type
            next unless type_ok

            findings << Report::Finding.new(
              zone: ch.zone, owner: ch.owner, record_type: ch.record_type, code: "FREEZE_WINDOW",
              severity: "blocking",
              evidence: Report::Evidence.for_code("FREEZE_WINDOW", fz.freeze_id)
            )
          end
        end
        findings
      end
    end
  end
end
