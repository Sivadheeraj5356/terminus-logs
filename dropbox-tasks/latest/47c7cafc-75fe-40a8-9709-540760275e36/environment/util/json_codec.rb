# frozen_string_literal: true

require "json"

module Util
  module JsonCodec
    module_function

    def write(path, obj)
      File.write(path, JSON.pretty_generate(obj) + "\n")
    end

    def read(path)
      JSON.parse(File.read(path), symbolize_names: true)
    end
  end
end
