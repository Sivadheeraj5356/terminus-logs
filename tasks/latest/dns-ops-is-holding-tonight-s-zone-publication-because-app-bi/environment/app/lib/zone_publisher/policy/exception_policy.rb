# frozen_string_literal: true

require "zone_publisher/report/model"

module ZonePublisher
  module Policy
    module ExceptionPolicy
      module_function

      def partition(findings, exceptions, _changes)
        blocked = []
        suppressed = []
        findings.each do |f|
          ex = exceptions.find { |e| e.code == f.code }
          if ex
            suppressed << Report::Suppressed.new(
              zone: f.zone, owner: f.owner, record_type: f.record_type, code: f.code,
              exception_id: ex.exception_id, reason: ex.reason, evidence: f.evidence
            )
          else
            blocked << f
          end
        end
        [blocked, suppressed]
      end
    end
  end
end
