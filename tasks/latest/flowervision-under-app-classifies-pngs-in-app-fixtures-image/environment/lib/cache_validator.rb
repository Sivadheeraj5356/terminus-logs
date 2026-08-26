# frozen_string_literal: true

# BUG: always returns true — never rejects bad cache entries.
class CacheValidator
  def self.valid?(entry)
    true
  end
end