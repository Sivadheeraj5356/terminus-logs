# frozen_string_literal: true

# row_digest: sort rows by unit_id; for each row concatenate
#   unit_id|bind_rc|lock_rc|unit_rc|drift_code|facet_hex
# joined by newlines; hash with idx-weighted char sum mod 2^64; take low 32 bits as 8 hex chars.
# span_band: max absolute drift_code across rows.

require "optparse"

require_relative "../util/digest"
require_relative "../util/json_codec"
require_relative "../engine/pipeline"
require_relative "../tools/gauge_mux"

module Pilot
  module Entry
    ENV_ROOT = ENV.fetch("ENV_ROOT", "/app/environment")
    OUT_PATH = "/app/output/ops_row_report.json"

    module_function

    def run(argv)
      opts = parse_argv(argv)
      rows = Engine::Pipeline.build_rows(ENV_ROOT, opts)
      gauge_tag = Tools::GaugeMux.early_tag(rows)
      coherent = rows.all? do |r|
        r[:bind_rc] == 1 && r[:lock_rc] == 1 && r[:unit_rc] == 1 && r[:drift_code] == 0
      end
      sync_label = coherent ? "steady" : gauge_tag

      summary = {
        rows_total: rows.length,
        sync_label: sync_label,
        span_band: Tools::SummaryMux.span_band(rows),
        row_digest: Util::DigestUtil.row_digest(rows)
      }

      report = { rows: rows, summary: summary }
      FileUtils.mkdir_p(File.dirname(OUT_PATH))
      Util::JsonCodec.write(OUT_PATH, report)
    end

    def parse_argv(argv)
      args = argv.dup
      args.shift if args.first == "run"
      opts = { hook: "run" }
      OptionParser.new do |o|
        o.on("--hook VAL") { |v| opts[:hook] = v }
        o.on("--resume VAL", Integer) { |v| opts[:resume] = v }
        o.on("--ord VAL") { |v| opts[:ord] = v }
      end.parse!(args)
      opts
    end
  end
end

require "fileutils"
