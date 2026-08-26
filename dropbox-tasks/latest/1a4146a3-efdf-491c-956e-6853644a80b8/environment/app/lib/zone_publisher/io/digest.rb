# frozen_string_literal: true

require "digest"

module ZonePublisher
  module Io
    module DigestUtil
      module_function

      def sha256_file(path)
        Digest::SHA256.file(path).hexdigest
      end
    end
  end
end
