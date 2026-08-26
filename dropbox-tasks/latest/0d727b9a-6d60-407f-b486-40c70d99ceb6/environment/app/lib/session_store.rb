require 'securerandom'

# In-memory session storage keyed by session token UUID.
class SessionStore
  Session = Struct.new(:id, :created_at, :last_active, :data, keyword_init: true)

  def initialize(timeout_seconds)
    @timeout = timeout_seconds.to_i
    @store   = {}
  end

  def create
    id      = SecureRandom.uuid
    now     = Time.now
    session = Session.new(id: id, created_at: now, last_active: now, data: {})
    @store[id] = session
    id
  end

  def fetch(id)
    session = @store[id]
    return nil unless session

    if expired?(session)
      @store.delete(id)
      return nil
    end

    session.last_active = Time.now
    session
  end

  def delete(id)
    @store.delete(id)
  end

  def count
    @store.size
  end

  private

  def expired?(session)
    (Time.now - session.last_active) > @timeout
  end
end
