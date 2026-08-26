# frozen_string_literal: true

module Util
  module DigestUtil
    module_function

    def facet_hex(step_ix, family_ix, prev_family, mux_val)
      mask = (1 << 64) - 1
      base = (mux_val & mask) ^ ((step_ix & 0xFFFF) << 16) ^ (family_ix & 0xFFFF) ^ (prev_family & 0xFFFFFFFF)
      format("%016x", base & ((1 << 64) - 1))
    end

    def row_digest(rows)
      parts = rows.map do |row|
        format(
          "%s|%d|%d|%d|%d|%s",
          row[:unit_id],
          row[:bind_rc],
          row[:lock_rc],
          row[:unit_rc],
          row[:drift_code],
          row[:facet_hex]
        )
      end
      payload = parts.sort.join("\n")
      mask64 = (1 << 64) - 1
      total = 0
      payload.each_char.with_index(1) do |ch, idx|
        total = (total + ((idx * ch.ord) & mask64)) & mask64
      end
      format("%08x", total & 0xFFFFFFFF)
    end
  end
end
