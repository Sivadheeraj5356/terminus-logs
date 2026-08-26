# frozen_string_literal: true

def fmt_cert_row(row)
  return "" unless row.is_a?(Hash)
  [row["t"], row["kid"], row["plan"], row["e_tag"]].map(&:to_s).join("|")
end
