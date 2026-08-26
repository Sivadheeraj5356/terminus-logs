# frozen_string_literal: true
require "json"
require "fileutils"

module PinStore
  SCRATCH = File.expand_path(".scratch/cur.json", __dir__)

  def self.load_cur
    return {} unless File.file?(SCRATCH)
    JSON.parse(File.read(SCRATCH))
  rescue
    {}
  end

  def self.write_cur(h)
    FileUtils.mkdir_p(File.dirname(SCRATCH))
    File.write(SCRATCH, JSON.generate(h))
  end
end
