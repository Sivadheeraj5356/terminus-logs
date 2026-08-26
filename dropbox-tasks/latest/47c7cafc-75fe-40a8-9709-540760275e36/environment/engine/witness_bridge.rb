# frozen_string_literal: true

require "json"

module Engine
  module WitnessBridge
    module_function

    def witness_ok?(witness_path, rows)
      witness = JSON.parse(File.read(witness_path))
      segments = witness.fetch("segments")
      return false if segments.empty?

      arm_sum = segments.sum { |s| s["arm"].to_i }
      facet_sum = rows.sum { |r| r[:facet_hex][0, 4].to_i(16) }
      witness.fetch("witness") == format("%08x", (arm_sum ^ facet_sum) & 0xFFFFFFFF)
    end
  end
end
