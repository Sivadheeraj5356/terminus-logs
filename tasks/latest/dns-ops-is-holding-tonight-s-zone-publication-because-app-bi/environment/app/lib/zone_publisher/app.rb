# frozen_string_literal: true

require "zone_publisher/cli/args"
require "zone_publisher/cli/errors"
require "zone_publisher/io/atomic_writer"
require "zone_publisher/io/digest"
require "zone_publisher/records/zone_file"
require "zone_publisher/records/journal"
require "zone_publisher/records/freezes"
require "zone_publisher/records/exceptions"
require "zone_publisher/policy/candidate_zone"
require "zone_publisher/policy/soa_policy"
require "zone_publisher/policy/cname_policy"
require "zone_publisher/policy/delegation_policy"
require "zone_publisher/policy/wildcard_policy"
require "zone_publisher/policy/freeze_policy"
require "zone_publisher/policy/exception_policy"
require "zone_publisher/policy/record_policy"
require "zone_publisher/report/canonical_json"
require "zone_publisher/report/sort"
require "zone_publisher/report/model"
require "zone_publisher/decoy/audit_banner"

module ZonePublisher
  module App
    module_function

    def run(argv)
      begin
        paths = Cli::Args.parse(argv)
      rescue Cli::FatalError => e
        warn e.message
        return 2
      end

      Io::AtomicWriter.write(paths.report, "{\n  \"partial\": true\n}\n")

      begin
        zone_rrs = Records::ZoneFile.load(paths.zone)
        changes = Records::Journal.load(paths.journal)
        freezes = Records::Freezes.load(paths.freezes)
        exceptions = Records::Exceptions.load(paths.exceptions)
      rescue Cli::FatalError => e
        warn e.message
        return 2
      end

      if changes.empty?
        zone = guess_zone(zone_rrs)
      else
        zones = changes.map(&:zone).uniq
        if zones.length != 1
          warn "active journal spans multiple zones"
          return 2
        end
        zone = zones.first
      end

      applied = Policy::CandidateZone.apply(zone_rrs, changes)
      findings = []
      findings.concat(applied.findings)
      findings.concat(Policy::SoaPolicy.evaluate(zone, zone_rrs, applied.records))
      findings.concat(Policy::CnamePolicy.evaluate(zone, applied.records))
      findings.concat(Policy::DelegationPolicy.evaluate(zone, applied.records))
      findings.concat(Policy::WildcardPolicy.evaluate(zone, applied.records))
      findings.concat(Policy::RecordPolicy.evaluate(zone, applied.records))
      findings.concat(Policy::FreezePolicy.evaluate(changes, freezes))

      blocked, suppressed = Policy::ExceptionPolicy.partition(findings, exceptions, changes)
      blocked = Report::Sort.findings(blocked)
      suppressed = Report::Sort.suppressed(suppressed)

      soa = applied.records.find { |rr| rr.type == "SOA" && rr.owner == zone }
      soa_serial = soa ? Integer(soa.rdata.split(/\s+/)[2]) : 0
      delags = Policy::DelegationPolicy.delegation_owners(zone, applied.records)

      report = {
        "format_version" => 1,
        "inputs" => {
          "zone_sha256" => Io::DigestUtil.sha256_file(paths.zone),
          "journal_sha256" => Io::DigestUtil.sha256_file(paths.journal),
          "freezes_sha256" => Io::DigestUtil.sha256_file(paths.freezes),
          "exceptions_sha256" => Io::DigestUtil.sha256_file(paths.exceptions)
        },
        "summary" => {
          "publishable" => blocked.empty?,
          "findings" => blocked.length,
          "suppressed" => suppressed.length,
          "active_changes" => changes.length
        },
        "findings" => blocked.map { |f| finding_hash(f) },
        "suppressed" => suppressed.map { |f| suppressed_hash(f) },
        "candidate" => {
          "zone" => zone,
          "soa_serial" => soa_serial,
          "record_count" => applied.records.length,
          "delegation_count" => delags.length
        }
      }

      body = Report::CanonicalJson.dump(report)
      Io::AtomicWriter.write(paths.report, body)
      puts "zone-publisher: report written"
      _ = Decoy::AuditBanner.render(zone, changes.length)
      blocked.empty? ? 0 : 1
    end

    def finding_hash(f)
      {
        "zone" => f.zone,
        "owner" => f.owner,
        "record_type" => f.record_type,
        "code" => f.code,
        "severity" => f.severity,
        "evidence" => f.evidence
      }
    end

    def suppressed_hash(f)
      {
        "zone" => f.zone,
        "owner" => f.owner,
        "record_type" => f.record_type,
        "code" => f.code,
        "exception_id" => f.exception_id,
        "reason" => f.reason,
        "evidence" => f.evidence
      }
    end

    def guess_zone(rrs)
      soa = rrs.find { |rr| rr.type == "SOA" }
      soa ? soa.owner : (rrs.first ? rrs.first.owner : "")
    end

    private_class_method :finding_hash, :suppressed_hash, :guess_zone
  end
end
