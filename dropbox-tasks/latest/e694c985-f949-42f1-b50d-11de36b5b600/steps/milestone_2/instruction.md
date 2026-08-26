Legacy Redis keys still use the unsafe `flower_prediction:*` layout and collide across users/models. With Redis running, seed via `bundle exec ruby /app/scripts/seed_cache.rb`, then implement `/app/lib/redis_migration.rb` per `/app/docs/cache_policy.md` (ALL policy rules are mandatory).

`RedisKeyBuilder.build(model:, image_id:, user_id:)` must emit user-scoped namespaced keys. `RedisMigration` needs `discover_legacy_keys`, `migrate_key`, `remove_stale_features`, and `run!` writing `/tmp/redis_migration_manifest.json` with `schema_version` `1` plus integer `migrated`, `removed`, and `failed`. Migrate both legacy key shapes in the policy and purge stale entries (corrupt JSON, missing metadata, old versions, expired records, checksum or mean_rgb mismatch).

Validate with `bundle exec ruby /app/scripts/run_migration.rb` and `bundle exec ruby /app/scripts/test_redis_migration.rb`.
