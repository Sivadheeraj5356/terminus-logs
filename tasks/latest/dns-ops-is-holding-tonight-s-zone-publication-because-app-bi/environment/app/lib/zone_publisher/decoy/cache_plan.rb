# frozen_string_literal: true

require "zone_publisher/dns/name"

module ZonePublisher
  module Decoy
    module CachePlan
      Plan = Struct.new(:zone, :owners, :ttl_hint, keyword_init: true)

      module_function

      def for_zone(zone, owners)
        Plan.new(zone: zone, owners: owners.map { |o| Dns::Name.normalize(o) }.uniq.sort, ttl_hint: 300)
      end

      def render(plan)
        (["# cache plan for #{plan.zone}"] + plan.owners.map { |o| "#{o} ttl=#{plan.ttl_hint}" }).join("\n")
      end
    end
  end
end
