# frozen_string_literal: true

module Q9
  module IngressH
    module_function

    def ingest(path)
      File.readlines(path).map(&:strip).reject(&:empty?).map { |ln| JSON.parse(ln) }
    rescue StandardError
      []
    end
  end
end

require 'json'
