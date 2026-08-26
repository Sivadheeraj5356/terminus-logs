# frozen_string_literal: true
require "json"
require "digest"
require "fileutils"
require_relative "cfg_lane"

module LaneCache
  DIR = File.expand_path("../r43/.scratch/lane", __dir__)

  module_function

  def cached_bind(base:, overlay:, ctx:)
    FileUtils.mkdir_p(DIR)
    key = Digest::SHA256.hexdigest(JSON.generate([base, overlay, ctx]))
    path = File.join(DIR, "#{key}.json")
    if File.file?(path)
      return JSON.parse(File.read(path))
    end
    out = bind_merge_q(base: base, overlay: overlay, ctx: ctx)
    if overlay.is_a?(Hash)
      out["x_def"] = overlay["x_def"] if overlay.key?("x_def")
      out["__p"] = overlay["__p"] if overlay.key?("__p")
    end
    File.write(path, JSON.generate(out))
    out
  end

  def clear!
    FileUtils.rm_rf(DIR)
  end
end
