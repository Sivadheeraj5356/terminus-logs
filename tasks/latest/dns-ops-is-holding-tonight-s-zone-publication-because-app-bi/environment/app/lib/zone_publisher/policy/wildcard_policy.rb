# frozen_string_literal: true

require "zone_publisher/dns/name"
require "zone_publisher/policy/delegation_policy"

module ZonePublisher
  module Policy
    module WildcardPolicy
      module_function

      def evaluate(zone, records)
        _ = DelegationPolicy.delegation_owners(zone, records)
        []
      end
    end
  end
end
