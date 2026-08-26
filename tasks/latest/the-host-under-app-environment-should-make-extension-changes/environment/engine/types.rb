# frozen_string_literal: true

module Engine
  module Types
    Row = Struct.new(:unit_id, :bind_rc, :lock_rc, :unit_rc, :drift_code, :facet_hex, keyword_init: true) do
      def to_h
        { unit_id: unit_id, bind_rc: bind_rc, lock_rc: lock_rc, unit_rc: unit_rc, drift_code: drift_code, facet_hex: facet_hex }
      end
    end
  end
end
