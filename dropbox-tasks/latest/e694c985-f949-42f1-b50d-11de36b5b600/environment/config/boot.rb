# frozen_string_literal: true

require "bundler/setup"
Bundler.require(:default)

require "json"
require "digest"
require "open3"
require "fileutils"
require "rack"

APP_ROOT = File.expand_path("..", __dir__)
$LOAD_PATH.unshift(File.join(APP_ROOT, "lib"))
$LOAD_PATH.unshift(File.join(APP_ROOT, "app", "services"))
$LOAD_PATH.unshift(File.join(APP_ROOT, "app", "controllers"))

Dir[File.join(APP_ROOT, "lib", "*.rb")].sort.each { |f| require f }
Dir[File.join(APP_ROOT, "app", "services", "*.rb")].sort.each { |f| require f }

module FlowerVision
  FEATURE_VERSION = "v2"
  MODEL_NAME = "flower"
  FIXTURES_DIR = File.join(APP_ROOT, "fixtures", "images")
  OUTPUT_DIR = File.join(APP_ROOT, "output")
  TMP_DIR = File.join(APP_ROOT, "tmp")
  MANIFEST_PATH = "/tmp/redis_migration_manifest.json"
  AUDIT_PATH = File.join(OUTPUT_DIR, "inference_audit.json")

  def self.redis
    @redis ||= Redis.new(url: ENV.fetch("REDIS_URL", "redis://127.0.0.1:6379/0"))
  end
end
