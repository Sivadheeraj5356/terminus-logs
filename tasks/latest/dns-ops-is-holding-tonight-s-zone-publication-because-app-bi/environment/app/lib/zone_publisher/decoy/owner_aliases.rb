# frozen_string_literal: true

module ZonePublisher
  module Decoy
    module OwnerAliases
      TABLE = {
        "www" => "web-frontend",
        "mail" => "mx-primary",
        "ns1" => "auth-a"
      }.freeze

      module_function

      def expand(label)
        TABLE.fetch(label, label)
      end
    end
  end
end
