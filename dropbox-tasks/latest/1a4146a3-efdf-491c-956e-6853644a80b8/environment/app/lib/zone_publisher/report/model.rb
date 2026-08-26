# frozen_string_literal: true

module ZonePublisher
  module Report
    Finding = Struct.new(:zone, :owner, :record_type, :code, :severity, :evidence, keyword_init: true)
    Suppressed = Struct.new(:zone, :owner, :record_type, :code, :exception_id, :reason, :evidence, keyword_init: true)
    CandidateInfo = Struct.new(:zone, :soa_serial, :record_count, :delegation_count, keyword_init: true)
  end
end
