# frozen_string_literal: true

require 'json'

module Util
  module JsonRead
    module_function

    def load_ndjson(path)
      File.readlines(path).map(&:strip).reject(&:empty?).map { |line| JSON.parse(line) }
    end

    def load_jsonl(path)
      load_ndjson(path)
    end
  end
end
