# frozen_string_literal: true

require_relative 'pipeline'

module Engine
  module WaveRunner
    module_function

    def run_case(root, case_id)
      Engine::Pipeline::PROFILE_BANDS.flat_map do |mode_id|
        Engine::Pipeline.new(root: root, case_id: case_id, mode_id: mode_id).run!
      end
    end
  end
end
