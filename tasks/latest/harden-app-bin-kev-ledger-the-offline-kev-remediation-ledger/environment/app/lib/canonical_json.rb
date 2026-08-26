require 'json'

module CanonicalJson
  module_function

  def dump(value)
    JSON.generate(sort_value(value)) + "\n"
  end

  def sort_value(value)
    case value
    when Hash
      value.keys.sort.each_with_object({}) { |key, out| out[key] = sort_value(value[key]) }
    when Array
      value.map { |item| sort_value(item) }
    else
      value
    end
  end
end
