# frozen_string_literal: true

require "zone_publisher/cli/errors"

module ZonePublisher
  module Cli
    Paths = Struct.new(:zone, :journal, :freezes, :exceptions, :report, keyword_init: true)

    module Args
      REQUIRED = %w[--zone --journal --freezes --exceptions --report].freeze

      module_function

      def parse(argv)
        seen = {}
        values = {}
        i = 0
        while i < argv.length
          name = argv[i]
          raise FatalError, "unexpected argument #{name.inspect}" unless name.start_with?("--")
          raise FatalError, "inline flag values are not supported: #{name}" if name.include?("=")
          raise FatalError, "missing value for #{name}" if i + 1 >= argv.length

          val = argv[i + 1]
          raise FatalError, "duplicate flag #{name}" if seen[name]

          seen[name] = true
          case name
          when "--zone", "--journal", "--freezes", "--exceptions", "--report"
            values[name] = val
          else
            raise FatalError, "unknown flag #{name}"
          end
          i += 2
        end
        REQUIRED.each do |flag|
          raise FatalError, "missing required flag #{flag}" if values[flag].to_s.empty?
        end
        Paths.new(
          zone: values["--zone"],
          journal: values["--journal"],
          freezes: values["--freezes"],
          exceptions: values["--exceptions"],
          report: values["--report"]
        )
      end
    end
  end
end
