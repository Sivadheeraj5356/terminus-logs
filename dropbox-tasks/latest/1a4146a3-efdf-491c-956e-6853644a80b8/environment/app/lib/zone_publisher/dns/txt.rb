# frozen_string_literal: true

module ZonePublisher
  module Dns
    module Txt
      module_function

      def canonicalize(rdata)
        rdata.to_s.gsub('"', "").gsub(/\s+/, " ").strip
      end

      def canonical?(rdata)
        canonicalize(rdata) == rdata.to_s
      end
    end
  end
end
