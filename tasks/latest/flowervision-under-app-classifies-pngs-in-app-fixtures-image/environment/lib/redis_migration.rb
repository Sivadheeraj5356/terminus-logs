# frozen_string_literal: true

# BUG: legacy key format flower_prediction:<id> collides across models/users.
class RedisKeyBuilder
  def self.build(model:, image_id:, user_id: "default")
    "flower_prediction:#{image_id}"
  end
end

class RedisMigration
  def self.discover_legacy_keys
    raise NotImplementedError, "RedisMigration.discover_legacy_keys is incomplete"
  end

  def self.migrate_key(old_key)
    raise NotImplementedError, "RedisMigration.migrate_key is incomplete"
  end

  def self.remove_stale_features
    raise NotImplementedError, "RedisMigration.remove_stale_features is incomplete"
  end

  def self.run!
    raise NotImplementedError, "RedisMigration.run! is incomplete"
  end
end
