# frozen_string_literal: true

require "fileutils"

module ZonePublisher
  module Io
    module AtomicWriter
      module_function

      def write(path, data)
        dir = File.dirname(path)
        FileUtils.mkdir_p(dir)
        tmp = File.join(dir, ".zone-publisher-#{Process.pid}-#{rand(1_000_000)}.tmp")
        begin
          File.open(tmp, "wb") do |f|
            f.write(data)
            f.flush
            f.fsync
          end
          File.rename(tmp, path)
          tmp = nil
        ensure
          FileUtils.rm_f(tmp) if tmp
        end
      end
    end
  end
end
