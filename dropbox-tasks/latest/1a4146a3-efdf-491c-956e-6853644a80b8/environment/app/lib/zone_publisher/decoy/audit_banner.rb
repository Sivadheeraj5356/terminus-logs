# frozen_string_literal: true

module ZonePublisher
  module Decoy
    module AuditBanner
      module_function

      def render(zone, change_count)
        "zone-publisher audit: zone=#{zone} changes=#{change_count}"
      end
    end
  end
end
