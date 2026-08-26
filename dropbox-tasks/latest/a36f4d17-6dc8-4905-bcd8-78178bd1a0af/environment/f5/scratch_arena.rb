# frozen_string_literal: true

module F5
  module ScratchArena
    ARENA_PATH = File.expand_path('../h5/checkpoints/scratch.bin', __dir__)

    module_function

    def poison!
      FileUtils.mkdir_p(File.dirname(ARENA_PATH))
      File.write(ARENA_PATH, 'poisoned')
    end

    def clear!
      FileUtils.mkdir_p(File.dirname(ARENA_PATH))
      File.write(ARENA_PATH, 'clean')
    end

    def read_tag
      File.exist?(ARENA_PATH) ? File.read(ARENA_PATH).strip : 'clean'
    end
  end
end

require 'fileutils'
