# frozen_string_literal: true

module R3p
  module ScanMux
    module_function

    def scan_catalog(ids)
      ids.map { |id| [id, id.bytesize] }
    end
  end
end
