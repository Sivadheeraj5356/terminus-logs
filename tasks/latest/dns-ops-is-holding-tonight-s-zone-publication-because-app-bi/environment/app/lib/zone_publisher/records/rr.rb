# frozen_string_literal: true

module ZonePublisher
  module Records
    RR = Struct.new(:owner, :ttl, :klass, :type, :rdata, keyword_init: true) do
      def identity
        [owner.downcase, type.upcase, rdata]
      end

      def owner_type
        [owner.downcase, type.upcase]
      end
    end

    JournalChange = Struct.new(
      :change_id, :seq, :action, :zone, :owner, :ttl, :record_type, :rdata,
      :effective_utc, :correction_of, :reason, keyword_init: true
    )

    FreezeRow = Struct.new(
      :freeze_id, :zone, :owner_suffix, :record_type, :start_utc, :end_utc, :reason,
      keyword_init: true
    )

    ExceptionRow = Struct.new(
      :exception_id, :zone, :owner_suffix, :record_type, :code, :start_utc, :end_utc, :reason,
      keyword_init: true
    )

    SUPPORTED_TYPES = %w[SOA NS A AAAA CNAME MX TXT CAA DS DNSKEY RRSIG NSEC].freeze
    DNSSEC_SIDE = %w[RRSIG NSEC].freeze
    ACTIONS = %w[add delete replace].freeze
    FINDING_CODES = %w[
      SERIAL_NOT_ADVANCED APEX_CNAME SOA_COUNT CNAME_CONFLICT DELEGATION_GLUE_MISSING
      WILDCARD_BELOW_DELEGATION FREEZE_WINDOW TXT_CANONICAL TTL_OUT_OF_RANGE UNKNOWN_DELETE
    ].freeze
  end
end
