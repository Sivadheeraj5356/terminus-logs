# frozen_string_literal: true

module ZonePublisher
  module Report
    module Evidence
      module_function

      def for_code(code, detail = nil)
        base = {
          "SERIAL_NOT_ADVANCED" => "candidate SOA serial is not advanced",
          "APEX_CNAME" => "CNAME present at zone apex",
          "SOA_COUNT" => "apex SOA count is not exactly one",
          "CNAME_CONFLICT" => "CNAME owner has conflicting non-DNSSEC records",
          "DELEGATION_GLUE_MISSING" => "in-zone delegated nameserver lacks glue",
          "WILDCARD_BELOW_DELEGATION" => "wildcard owner lies below a delegated zone cut",
          "FREEZE_WINDOW" => "active change overlaps freeze window",
          "TXT_CANONICAL" => "TXT rdata is not in canonical form",
          "TTL_OUT_OF_RANGE" => "TTL outside allowed range 30..86400",
          "UNKNOWN_DELETE" => "delete targets a record absent from the candidate"
        }
        msg = base.fetch(code, code)
        detail ? "#{msg} #{detail}" : msg
      end
    end
  end
end
