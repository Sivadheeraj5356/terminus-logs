# frozen_string_literal: true

require "tomlrb"

module Util
  module TomlLoader
    module_function

    def load(path)
      Tomlrb.load_file(path)
    end
  end
end
