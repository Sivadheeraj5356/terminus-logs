# frozen_string_literal: true
require "json"

def emit_rows_pack(rows)
  list = rows.is_a?(Array) ? rows : []
  JSON.generate(list)
end
