require 'set'

class NonceStore
  def initialize
    @seen = Set.new
  end

  def record!(nonce)
    return false if @seen.include?(nonce)
    @seen.add(nonce)
    true
  end
end
