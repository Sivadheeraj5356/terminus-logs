#!/bin/bash
set -euo pipefail
cat > /app/bin/kev-ledger <<'RUBY'
#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'
require 'digest'
require 'date'
require 'pathname'
require 'openssl'
require 'base64'

APP_ROOT = Pathname.new('/app').freeze
SUCCESS_FILES = ['kev-ledger.json', 'entries.tsv', 'actions.tsv', 'vendor-summary.tsv', 'rebuild-ledger.json', 'manifest.sha256'].freeze
STATE_REL = File.join('state', 'kev-ledger.state.json')
VALID_ACTIONS = ['defer', 'escalate', 'suppress', 'clear'].freeze

CWE_CLASSES = {
  'code-execution' => ['CWE-78', 'CWE-94', 'CWE-502', 'CWE-306', 'CWE-918'],
  'path-traversal' => ['CWE-22', 'CWE-61'],
  'auth-integrity' => ['CWE-284', 'CWE-287', 'CWE-347'],
  'input-validation' => ['CWE-20'],
  'memory-safety' => ['CWE-119', 'CWE-787']
}.freeze
CWE_LOOKUP = CWE_CLASSES.flat_map { |klass, cwes| cwes.map { |cwe| [cwe, klass] } }.to_h.freeze
STATUS_RANK = {'overdue' => 0, 'due_soon' => 1, 'deferred' => 2, 'open' => 3}.freeze
PRIORITY_RANK = {'emergency' => 0, 'accelerated' => 1, 'standard' => 2}.freeze

module Canon
  module_function

  def sort_value(value)
    case value
    when Hash
      value.keys.sort.each_with_object({}) { |key, out| out[key] = sort_value(value[key]) }
    when Array
      value.map { |item| sort_value(item) }
    else
      value
    end
  end

  def dump(value)
    JSON.generate(sort_value(value)) + "\n"
  end
end

class RunFailure < StandardError
  attr_reader :reason, :details

  def initialize(reason, details = {})
    super(reason)
    @reason = reason
    @details = details
  end
end

def raw_traversal?(path)
  Pathname.new(path).each_filename.any? { |part| part == '..' }
end

def within?(path, root)
  path.to_s == root.to_s || path.to_s.start_with?(root.to_s + '/')
end

def clean_input_path(path, reason = 'unsafe_path', require_file: false, unreadable_reason: nil)
  raw = path.to_s
  raise RunFailure.new(reason, {'path' => raw}) unless Pathname.new(raw).absolute?
  raise RunFailure.new(reason, {'path' => raw}) if raw_traversal?(raw)
  lexical = Pathname.new(raw).cleanpath
  raise RunFailure.new(reason, {'path' => raw}) unless within?(lexical, APP_ROOT)
  begin
    resolved = lexical.realpath
  rescue Errno::ENOENT, Errno::EACCES, Errno::ELOOP
    raise RunFailure.new(unreadable_reason || reason, {'path' => raw, 'message' => 'missing'})
  end
  raise RunFailure.new(reason, {'path' => raw}) unless within?(resolved, APP_ROOT)
  if require_file && !File.file?(resolved.to_s)
    raise RunFailure.new(unreadable_reason || reason, {'path' => raw, 'message' => 'missing'})
  end
  resolved
end

def clean_output_path(path, reason = 'unsafe_path')
  raw = path.to_s
  candidate = Pathname.new(raw)
  raise RunFailure.new(reason, {'path' => raw}) unless candidate.absolute?
  raise RunFailure.new(reason, {'path' => raw}) if raw_traversal?(raw)
  lexical = candidate.cleanpath
  raise RunFailure.new(reason, {'path' => raw}) unless within?(lexical, APP_ROOT)

  begin
    root = APP_ROOT.realpath
    relative = lexical.relative_path_from(APP_ROOT)
  rescue ArgumentError, Errno::ENOENT, Errno::EACCES, Errno::ELOOP
    raise RunFailure.new(reason, {'path' => raw})
  end

  lexical_cursor = APP_ROOT
  resolved_cursor = root
  missing = false
  parts = relative.each_filename.to_a
  parts.each_with_index do |part, index|
    lexical_cursor = lexical_cursor.join(part)
    if missing
      resolved_cursor = resolved_cursor.join(part)
      next
    end

    begin
      stat = File.lstat(lexical_cursor.to_s)
    rescue Errno::ENOENT
      missing = true
      resolved_cursor = resolved_cursor.join(part)
      next
    rescue Errno::EACCES, Errno::ELOOP
      raise RunFailure.new(reason, {'path' => raw})
    end

    begin
      resolved = lexical_cursor.realpath
    rescue Errno::ENOENT, Errno::EACCES, Errno::ELOOP
      # File.lstat succeeds for a dangling symlink, while realpath must not.
      raise RunFailure.new(reason, {'path' => raw})
    end
    raise RunFailure.new(reason, {'path' => raw}) unless within?(resolved, root)
    if index < parts.length - 1 && !File.directory?(resolved.to_s)
      raise RunFailure.new(reason, {'path' => raw})
    end
    if index == parts.length - 1 && !stat.symlink? && !stat.directory?
      raise RunFailure.new(reason, {'path' => raw})
    end
    if index == parts.length - 1 && stat.symlink? && !File.directory?(resolved.to_s)
      raise RunFailure.new(reason, {'path' => raw})
    end
    resolved_cursor = resolved
  end

  resolved_cursor = resolved_cursor.cleanpath
  raise RunFailure.new(reason, {'path' => raw}) unless within?(resolved_cursor, root)
  resolved_cursor
end

def clean_relative_input(base, relative, reason, suffix, unreadable_reason)
  raw = relative.to_s
  raise RunFailure.new(reason, {'path' => raw}) if Pathname.new(raw).absolute? || raw_traversal?(raw) || !raw.end_with?(suffix)
  lexical = base.join(raw).cleanpath
  raise RunFailure.new(reason, {'path' => raw}) unless within?(lexical, base)
  begin
    resolved = lexical.realpath
  rescue Errno::ENOENT, Errno::EACCES, Errno::ELOOP
    raise RunFailure.new(unreadable_reason, {'path' => raw})
  end
  raise RunFailure.new(reason, {'path' => raw}) unless within?(resolved, base.realpath)
  raise RunFailure.new(unreadable_reason, {'path' => raw}) unless File.file?(resolved.to_s)
  resolved
end

def load_json_file(path, reason)
  JSON.parse(File.binread(path.to_s))
rescue Errno::ENOENT
  raise RunFailure.new(reason, {'path' => path.to_s, 'message' => 'missing'})
rescue JSON::ParserError => e
  raise RunFailure.new(reason, {'path' => path.to_s, 'message' => e.message})
end

def load_trust_store(path)
  trust = load_json_file(path, 'trust_store_unreadable')
  unless trust.is_a?(Hash) && trust['schema_version'] == 'kev.trust.v1' && trust['publishers'].is_a?(Hash)
    raise RunFailure.new('trust_store_schema_invalid', {'path' => path.to_s})
  end
  trust
end

def publisher_key(trust, signer, untrusted_reason, details)
  publisher = trust['publishers'][signer]
  unless publisher.is_a?(Hash) && publisher['public_key'].is_a?(String)
    raise RunFailure.new(untrusted_reason, details.merge('signer' => signer))
  end
  key_path = clean_input_path(publisher['public_key'], 'unsafe_trust_key_path', require_file: true, unreadable_reason: 'trust_key_unreadable')
  key = OpenSSL::PKey.read(File.read(key_path.to_s))
  begin
    raw_public = key.raw_public_key
  rescue OpenSSL::PKey::PKeyError, NoMethodError => e
    raise RunFailure.new('trust_key_invalid', {'path' => key_path.to_s, 'signer' => signer, 'message' => e.message})
  end
  unless key.inspect.include?('oid=ED25519') && raw_public.bytesize == 32
    raise RunFailure.new('trust_key_invalid', {'path' => key_path.to_s, 'signer' => signer, 'message' => 'public key is not Ed25519'})
  end
  key
rescue OpenSSL::PKey::PKeyError => e
  raise RunFailure.new('trust_key_invalid', {'path' => key_path.to_s, 'signer' => signer, 'message' => e.message})
end

def verify_detached_signature(data_bytes, signature_path, signer, trust, untrusted_reason, unreadable_reason, invalid_reason, details)
  begin
    signature_bytes = File.binread(signature_path.to_s)
  rescue Errno::ENOENT, Errno::EACCES
    raise RunFailure.new(unreadable_reason, details.merge('signature' => signature_path.to_s))
  end
  begin
    signature = Base64.strict_decode64(signature_bytes.strip)
  rescue ArgumentError
    raise RunFailure.new(invalid_reason, details.merge('signature' => signature_path.to_s, 'signer' => signer))
  end
  key = publisher_key(trust, signer, untrusted_reason, details)
  verified = key.verify(nil, signature, data_bytes)
  raise RunFailure.new(invalid_reason, details.merge('signature' => signature_path.to_s, 'signer' => signer)) unless verified
rescue OpenSSL::PKey::PKeyError
  raise RunFailure.new(invalid_reason, details.merge('signature' => signature_path.to_s, 'signer' => signer))
end

def parse_date(value)
  return nil unless value.is_a?(String) && value.match?(/\A\d{4}-\d{2}-\d{2}\z/)
  Date.iso8601(value)
rescue Date::Error
  nil
end

def row_errors(row)
  errors = []
  required = %w[seq cveID vendorProject product vulnerabilityName dateAdded dueDate knownRansomwareCampaignUse notes cwes]
  required.each { |key| errors << "missing_#{key}" unless row.key?(key) }
  errors << 'seq_invalid' unless row['seq'].is_a?(Integer)
  errors << 'cve_invalid' unless row['cveID'].is_a?(String) && row['cveID'].match?(/\ACVE-\d{4}-\d{4,19}\z/)
  date_added = parse_date(row['dateAdded'])
  due_date = parse_date(row['dueDate'])
  errors << 'date_added_invalid' if date_added.nil?
  errors << 'due_date_invalid' if due_date.nil?
  errors << 'due_before_added' if date_added && due_date && due_date < date_added
  errors << 'ransomware_invalid' unless ['Known', 'Unknown'].include?(row['knownRansomwareCampaignUse'])
  %w[vendorProject product vulnerabilityName].each do |key|
    errors << "#{key}_blank" unless row[key].is_a?(String) && !row[key].strip.empty?
  end
  unless row['cwes'].is_a?(Array) && !row['cwes'].empty? && row['cwes'].all? { |cwe| cwe.is_a?(String) && cwe.match?(/\ACWE-\d+\z/) }
    errors << 'cwes_invalid'
  end
  errors.sort
end

def action_errors(row)
  errors = []
  required = %w[seq cve_id action owner ticket effective_date expires_on source]
  required.each { |key| errors << "missing_#{key}" unless row.key?(key) }
  errors << 'seq_invalid' unless row['seq'].is_a?(Integer)
  errors << 'cve_invalid' unless row['cve_id'].is_a?(String) && row['cve_id'].match?(/\ACVE-\d{4}-\d{4,19}\z/)
  errors << 'action_invalid' unless VALID_ACTIONS.include?(row['action'])
  %w[owner ticket source].each do |key|
    errors << "#{key}_blank" unless row[key].is_a?(String) && !row[key].strip.empty?
  end
  effective = parse_date(row['effective_date'])
  expires = parse_date(row['expires_on'])
  errors << 'effective_date_invalid' if effective.nil?
  errors << 'expires_on_invalid' if expires.nil?
  errors << 'expired_before_effective' if effective && expires && expires < effective
  errors.sort
end

def cwe_classes(cwes)
  cwes.map { |cwe| CWE_LOOKUP.fetch(cwe, 'other') }.uniq.sort
end

def priority_for(row, classes)
  added = Date.iso8601(row['dateAdded'])
  due = Date.iso8601(row['dueDate'])
  window = (due - added).to_i
  return 'emergency' if row['knownRansomwareCampaignUse'] == 'Known' || window <= 7
  return 'accelerated' if window <= 14 || classes.include?('code-execution')
  'standard'
end

def status_for(row, as_of, due_soon_days, active_action)
  return 'deferred' if active_action && active_action['action'] == 'defer'
  due = Date.iso8601(row['dueDate'])
  return 'overdue' if due < as_of
  return 'due_soon' if due <= as_of + due_soon_days
  'open'
end

def input_fingerprint(fragments)
  material = fragments.map do |frag|
    {'path' => frag.fetch('path'), 'sha256' => Digest::SHA256.hexdigest(frag.fetch('_bytes'))}
  end.sort_by { |x| x['path'] }
  Digest::SHA256.hexdigest(Canon.dump(material))
end

def actions_fingerprint(actions_path, action_bytes)
  material = {'path' => actions_path.to_s, 'sha256' => Digest::SHA256.hexdigest(action_bytes)}
  Digest::SHA256.hexdigest(Canon.dump(material))
end

def config_fingerprint(config_path, profile)
  Digest::SHA256.hexdigest(File.binread(config_path.to_s) + "\0" + profile)
end

def prepare_directory(path, reason)
  safe = clean_output_path(path.to_s, reason)
  FileUtils.mkdir_p(safe.to_s)
  clean_output_path(safe.to_s, reason)
end

def remove_direct_child(parent, name)
  path = parent.join(name)
  FileUtils.rm_rf(path.to_s) if File.exist?(path.to_s) || File.symlink?(path.to_s)
end

def remove_success(out_dir)
  SUCCESS_FILES.each { |name| remove_direct_child(out_dir, name) }
  state_parent = out_dir.join('state')
  if File.symlink?(state_parent.to_s) || (File.exist?(state_parent.to_s) && !File.directory?(state_parent.to_s))
    FileUtils.rm_rf(state_parent.to_s)
  elsif File.directory?(state_parent.to_s)
    remove_direct_child(state_parent, 'kev-ledger.state.json')
  end
end

def safe_write(path, bytes, reason)
  parent = prepare_directory(path.dirname, reason)
  target = parent.join(path.basename)
  remove_direct_child(parent, path.basename.to_s)
  File.open(target.to_s, File::WRONLY | File::CREAT | File::EXCL, 0o600) { |file| file.write(bytes) }
  target
rescue Errno::EEXIST, Errno::EISDIR, Errno::ENOTDIR, Errno::ELOOP, Errno::EACCES
  raise RunFailure.new(reason, {'path' => path.to_s})
end

def write_error(out_dir, profile, reason, details)
  safe_out = prepare_directory(out_dir, 'unsafe_output_path')
  remove_success(safe_out)
  report = {'schema_version' => 'kev.error.v1', 'profile' => profile, 'reason' => reason, 'details' => details}
  safe_write(safe_out.join('error-report.json'), Canon.dump(report), 'unsafe_output_path')
end

def write_tsv(path, header, rows)
  safe_write(path, ([header] + rows).map { |row| row.join("\t") }.join("\n") + "\n", 'unsafe_output_path')
end

def build_rebuild(entries_path, actions_path, vendor_path)
  entries_bytes = File.binread(entries_path.to_s)
  actions_bytes = File.binread(actions_path.to_s)
  vendor_bytes = File.binread(vendor_path.to_s)
  entry_lines = entries_bytes.lines(chomp: true)
  action_lines = actions_bytes.lines(chomp: true)
  vendor_lines = vendor_bytes.lines(chomp: true)
  {
    'schema_version' => 'kev.rebuild.v1',
    'entry_count' => [entry_lines.length - 1, 0].max,
    'action_count' => [action_lines.length - 1, 0].max,
    'vendor_count' => [vendor_lines.length - 1, 0].max,
    'entries_digest' => Digest::SHA256.hexdigest(entries_bytes),
    'actions_digest' => Digest::SHA256.hexdigest(actions_bytes),
    'vendor_summary_digest' => Digest::SHA256.hexdigest(vendor_bytes)
  }
end

def load_actions(action_bytes, as_of)
  valid_actions = []
  invalid_actions = []
  action_bytes.each_line(chomp: true).each_with_index do |line, idx|
    next if line.strip.empty?
    begin
      row = JSON.parse(line)
    rescue JSON::ParserError => e
      invalid_actions << {'seq' => nil, 'cve_id' => nil, 'errors' => ['json_invalid'], 'line' => idx + 1}
      next
    end
    unless row.is_a?(Hash)
      invalid_actions << {'seq' => nil, 'cve_id' => nil, 'errors' => ['json_object_required'], 'line' => idx + 1}
      next
    end
    errors = action_errors(row)
    if errors.empty?
      valid_actions << row
    else
      invalid_actions << {'seq' => row['seq'], 'cve_id' => row['cve_id'], 'errors' => errors, 'line' => idx + 1}
    end
  end
  invalid_actions.sort_by! { |r| [r['line'].to_i, r['cve_id'].to_s] }
  winners = {}
  valid_actions.each do |row|
    cve = row['cve_id']
    old = winners[cve]
    better = old.nil? || row['seq'] > old['seq'] || (row['seq'] == old['seq'] && row['source'] < old['source'])
    winners[cve] = row if better
  end
  actions = winners.keys.sort.map do |cve|
    row = winners[cve]
    applied = Date.iso8601(row['effective_date']) <= as_of && as_of <= Date.iso8601(row['expires_on'])
    {
      'cve_id' => cve,
      'action' => row['action'],
      'source' => row['source'],
      'seq' => row['seq'],
      'owner' => row['owner'].strip,
      'ticket' => row['ticket'].strip,
      'effective_date' => row['effective_date'],
      'expires_on' => row['expires_on'],
      'applied' => applied
    }
  end
  [actions, invalid_actions]
end

def main
  options = {
    index: '/app/data/catalog_fragments/index.json',
    config: '/app/config/profiles.json',
    actions: '/app/config/remediation_actions.jsonl',
    actions_signature: nil,
    actions_signer: 'agency-actions',
    trust_store: '/app/config/trusted_publishers.json',
    profile: 'bod26',
    state_dir: '/app/state',
    out_dir: '/app/out',
    resume_from: nil
  }
  OptionParser.new do |opts|
    opts.on('--index PATH') { |v| options[:index] = v }
    opts.on('--config PATH') { |v| options[:config] = v }
    opts.on('--actions PATH') { |v| options[:actions] = v }
    opts.on('--actions-signature PATH') { |v| options[:actions_signature] = v }
    opts.on('--actions-signer ID') { |v| options[:actions_signer] = v }
    opts.on('--trust-store PATH') { |v| options[:trust_store] = v }
    opts.on('--profile NAME') { |v| options[:profile] = v }
    opts.on('--state-dir PATH') { |v| options[:state_dir] = v }
    opts.on('--out-dir PATH') { |v| options[:out_dir] = v }
    opts.on('--resume-from PATH') { |v| options[:resume_from] = v }
  end.parse!

  out_dir = nil
  profile_name = options[:profile]

  begin
    out_dir = clean_output_path(options[:out_dir], 'unsafe_output_path')
    index_path = clean_input_path(options[:index], 'unsafe_index_path', require_file: true, unreadable_reason: 'index_unreadable')
    config_path = clean_input_path(options[:config], 'unsafe_config_path', require_file: true, unreadable_reason: 'config_unreadable')
    actions_path = clean_input_path(options[:actions], 'unsafe_actions_path', require_file: true, unreadable_reason: 'actions_unreadable')
    raise RunFailure.new('unsafe_actions_path', {'path' => options[:actions]}) unless actions_path.to_s.end_with?('.jsonl')
    raise RunFailure.new('actions_unreadable', {'path' => actions_path.to_s, 'message' => 'missing'}) unless File.file?(actions_path.to_s)
    actions_signature_value = options[:actions_signature] || "#{actions_path}.sig"
    actions_signature_path = clean_input_path(actions_signature_value, 'unsafe_actions_signature_path', require_file: true, unreadable_reason: 'actions_signature_unreadable')
    raise RunFailure.new('unsafe_actions_signature_path', {'path' => actions_signature_value}) unless actions_signature_path.to_s.end_with?('.sig')
    trust_path = clean_input_path(options[:trust_store], 'unsafe_trust_store_path', require_file: true, unreadable_reason: 'trust_store_unreadable')
    state_dir = clean_output_path(options[:state_dir], 'unsafe_state_path')
    resume_path = options[:resume_from] ? clean_input_path(options[:resume_from], 'unsafe_resume_path', require_file: true, unreadable_reason: 'resume_unreadable') : nil

    index = load_json_file(index_path, 'index_unreadable')
    config = load_json_file(config_path, 'config_unreadable')
    trust = load_trust_store(trust_path)
    raise RunFailure.new('index_schema_invalid', {'schema_version' => index.is_a?(Hash) ? index['schema_version'] : nil}) unless index.is_a?(Hash) && index['schema_version'] == 'kev.index.v1' && index['fragments'].is_a?(Array)
    raise RunFailure.new('config_schema_invalid', {'schema_version' => config.is_a?(Hash) ? config['schema_version'] : nil}) unless config.is_a?(Hash) && config['schema_version'] == 'kev.profiles.v1' && config['profiles'].is_a?(Hash)
    profile = config['profiles'][profile_name]
    raise RunFailure.new('unknown_profile', {'profile' => profile_name}) unless profile.is_a?(Hash)
    as_of = parse_date(config['as_of'])
    raise RunFailure.new('config_schema_invalid', {'field' => 'as_of'}) if as_of.nil?
    unless profile.key?('include_vendors') && profile['include_vendors'].is_a?(Array) &&
           profile['include_vendors'].all? { |v| v.is_a?(String) }
      raise RunFailure.new('config_schema_invalid', {'field' => 'include_vendors'})
    end
    unless profile.key?('include_cwe_classes') && profile['include_cwe_classes'].is_a?(Array) &&
           profile['include_cwe_classes'].all? { |v| v.is_a?(String) }
      raise RunFailure.new('config_schema_invalid', {'field' => 'include_cwe_classes'})
    end
    unless profile.key?('due_soon_days') && profile['due_soon_days'].is_a?(Integer)
      raise RunFailure.new('config_schema_invalid', {'field' => 'due_soon_days'})
    end
    due_soon_days = profile['due_soon_days']
    include_vendors = profile['include_vendors']
    include_classes = profile['include_cwe_classes']

    base = index_path.dirname
    fragments = index['fragments'].map do |frag|
      unless frag.is_a?(Hash) && frag['path'].is_a?(String) && frag['source'].is_a?(String) && frag['generation'].is_a?(Integer) && frag['signer'].is_a?(String) && frag['signature'].is_a?(String)
        raise RunFailure.new('index_schema_invalid', {'fragment' => frag})
      end
      rel = frag['path']
      path = clean_relative_input(base, rel, 'unsafe_fragment_path', '.jsonl', 'fragment_unreadable')
      signature_rel = frag['signature']
      signature_path = clean_relative_input(base, signature_rel, 'unsafe_fragment_signature_path', '.sig', 'fragment_signature_unreadable')
      details = {'path' => rel, 'source' => frag['source']}
      begin
        fragment_bytes = File.binread(path.to_s)
      rescue Errno::ENOENT, Errno::EACCES
        raise RunFailure.new('fragment_unreadable', {'path' => rel})
      end
      verify_detached_signature(
        fragment_bytes,
        signature_path,
        frag['signer'],
        trust,
        'untrusted_fragment_signer',
        'fragment_signature_unreadable',
        'fragment_signature_invalid',
        details
      )
      frag.merge('_path' => path, '_signature_path' => signature_path, '_bytes' => fragment_bytes)
    end

    begin
      action_bytes = File.binread(actions_path.to_s)
    rescue Errno::ENOENT, Errno::EACCES
      raise RunFailure.new('actions_unreadable', {'path' => actions_path.to_s, 'message' => 'missing'})
    end
    verify_detached_signature(
      action_bytes,
      actions_signature_path,
      options[:actions_signer],
      trust,
      'untrusted_actions_signer',
      'actions_signature_unreadable',
      'actions_signature_invalid',
      {'path' => actions_path.to_s}
    )

    inp_fp = input_fingerprint(fragments)
    act_fp = actions_fingerprint(actions_path, action_bytes)
    cfg_fp = config_fingerprint(config_path, profile_name)

    if resume_path
      state = load_json_file(resume_path, 'resume_unreadable')
      unless state.is_a?(Hash) && state['schema_version'] == 'kev.state.v1' && state['profile'] == profile_name && state['config_fingerprint'] == cfg_fp && state['input_fingerprint'] == inp_fp && state['actions_fingerprint'] == act_fp
        raise RunFailure.new('resume_fingerprint_mismatch', {'resume_from' => resume_path.to_s})
      end
    end

    actions, invalid_actions = load_actions(action_bytes, as_of)
    actions_by_cve = actions.to_h { |action| [action['cve_id'], action] }

    valid_rows = []
    invalid_rows = []
    fragments.each do |frag|
      frag['_bytes'].each_line(chomp: true).each_with_index do |line, idx|
        next if line.strip.empty?
        begin
          row = JSON.parse(line)
        rescue JSON::ParserError => e
          invalid_rows << {'source' => frag['source'], 'generation' => frag['generation'], 'seq' => nil, 'cve_id' => nil, 'errors' => ['json_invalid'], 'line' => idx + 1, 'message' => e.message}
          next
        end
        unless row.is_a?(Hash)
          invalid_rows << {'source' => frag['source'], 'generation' => frag['generation'], 'seq' => nil, 'cve_id' => nil, 'errors' => ['json_object_required'], 'line' => idx + 1}
          next
        end
        errors = row_errors(row)
        if errors.empty?
          valid_rows << row.merge('_source' => frag['source'], '_generation' => frag['generation'])
        else
          invalid_rows << {
            'source' => frag['source'],
            'generation' => frag['generation'],
            'seq' => row['seq'],
            'cve_id' => row['cveID'],
            'errors' => errors,
            'line' => idx + 1
          }
        end
      end
    end
    invalid_rows.sort_by! { |r| [r['source'].to_s, r['generation'].to_i, r['line'].to_i, r['cve_id'].to_s] }

    winners = {}
    valid_rows.each do |row|
      cve = row['cveID']
      old = winners[cve]
      better = old.nil? || row['_generation'] > old['_generation'] ||
               (row['_generation'] == old['_generation'] && row['seq'] > old['seq']) ||
               (row['_generation'] == old['_generation'] && row['seq'] == old['seq'] && row['_source'] < old['_source'])
      winners[cve] = row if better
    end

    vendor_all = include_vendors.include?('*')
    vendor_set = include_vendors.map { |v| v.to_s.strip.downcase }
    class_set = include_classes.map(&:to_s)

    lineage = []
    entries = []
    winners.keys.sort.each do |cve|
      row = winners[cve]
      classes = cwe_classes(row['cwes'])
      profile_selected = (vendor_all || vendor_set.include?(row['vendorProject'].strip.downcase)) && !(classes & class_set).empty?
      action = actions_by_cve[cve]
      active_action = action && action['applied'] ? action : nil
      suppressed = active_action && active_action['action'] == 'suppress'
      selected = profile_selected && !suppressed
      lineage << {'cve_id' => cve, 'source' => row['_source'], 'generation' => row['_generation'], 'seq' => row['seq'], 'selected' => selected}
      next unless selected
      priority = priority_for(row, classes)
      priority = 'emergency' if active_action && active_action['action'] == 'escalate'
      entries << {
        'cve_id' => row['cveID'],
        'vendor' => row['vendorProject'].strip,
        'product' => row['product'].strip,
        'vulnerability_name' => row['vulnerabilityName'].strip,
        'date_added' => row['dateAdded'],
        'due_date' => row['dueDate'],
        'ransomware' => row['knownRansomwareCampaignUse'],
        'cwe_classes' => classes,
        'status' => status_for(row, as_of, due_soon_days, active_action),
        'priority' => priority,
        'source' => row['_source'],
        'generation' => row['_generation'],
        'seq' => row['seq'],
        'notes_digest' => Digest::SHA256.hexdigest(row['notes'])
      }
    end
    entries.sort_by! { |e| [STATUS_RANK[e['status']], PRIORITY_RANK[e['priority']], e['vendor'].downcase, e['product'].downcase, e['cve_id']] }

    by_status = entries.group_by { |e| e['status'] }.transform_values(&:length).sort.to_h
    by_priority = entries.group_by { |e| e['priority'] }.transform_values(&:length).sort.to_h
    by_vendor = entries.group_by { |e| e['vendor'] }.transform_values(&:length).sort.to_h
    by_action = actions.select { |a| a['applied'] }.group_by { |a| a['action'] }.transform_values(&:length).sort.to_h
    summary = {
      'profile' => profile_name,
      'as_of' => config['as_of'],
      'entry_count' => entries.length,
      'invalid_row_count' => invalid_rows.length,
      'action_count' => actions.length,
      'invalid_action_count' => invalid_actions.length,
      'by_status' => by_status,
      'by_priority' => by_priority,
      'by_vendor' => by_vendor,
      'by_action' => by_action,
      'input_fingerprint' => inp_fp,
      'actions_fingerprint' => act_fp
    }
    ledger = {
      'schema_version' => 'kev.ledger.v1',
      'summary' => summary,
      'entries' => entries,
      'actions' => actions,
      'invalid_rows' => invalid_rows,
      'invalid_actions' => invalid_actions,
      'lineage' => lineage
    }

    out_dir = prepare_directory(out_dir, 'unsafe_output_path')
    clean_output_path(out_dir.join('state').to_s, 'unsafe_output_path')
    remove_success(out_dir)
    out_state_dir = prepare_directory(out_dir.join('state'), 'unsafe_output_path')
    state_dir = prepare_directory(state_dir, 'unsafe_state_path')
    remove_direct_child(out_dir, 'error-report.json')
    ledger_path = out_dir.join('kev-ledger.json')
    entries_path = out_dir.join('entries.tsv')
    actions_tsv_path = out_dir.join('actions.tsv')
    vendor_path = out_dir.join('vendor-summary.tsv')
    rebuild_path = out_dir.join('rebuild-ledger.json')
    manifest_path = out_dir.join('manifest.sha256')
    state_path = out_dir.join(STATE_REL)

    safe_write(ledger_path, Canon.dump(ledger), 'unsafe_output_path')
    entry_rows = entries.map { |e| [e['cve_id'], e['vendor'], e['product'], e['status'], e['priority'], e['due_date'], e['ransomware'], e['cwe_classes'].join('|')] }
    write_tsv(entries_path, %w[cve_id vendor product status priority due_date ransomware cwe_classes], entry_rows)
    action_rows = actions.map { |a| [a['cve_id'], a['action'], a['applied'].to_s, a['owner'], a['ticket'], a['expires_on']] }
    write_tsv(actions_tsv_path, %w[cve_id action applied owner ticket expires_on], action_rows)
    vendor_rows = by_vendor.keys.sort_by(&:downcase).map do |vendor|
      es = entries.select { |e| e['vendor'] == vendor }
      counts = es.group_by { |e| e['priority'] }.transform_values(&:length)
      [vendor, es.length, counts.fetch('emergency', 0), counts.fetch('accelerated', 0), counts.fetch('standard', 0)]
    end
    write_tsv(vendor_path, %w[vendor entry_count emergency accelerated standard], vendor_rows)
    safe_write(rebuild_path, Canon.dump(build_rebuild(entries_path, actions_tsv_path, vendor_path)), 'unsafe_output_path')
    manifest_lines = ['actions.tsv', 'entries.tsv', 'kev-ledger.json', 'rebuild-ledger.json', 'vendor-summary.tsv'].map do |rel|
      "#{Digest::SHA256.file(out_dir.join(rel).to_s).hexdigest}  #{rel}"
    end.sort
    safe_write(manifest_path, manifest_lines.join("\n") + "\n", 'unsafe_output_path')
    ledger_digest = Digest::SHA256.file(ledger_path.to_s).hexdigest
    state = {
      'schema_version' => 'kev.state.v1',
      'profile' => profile_name,
      'config_fingerprint' => cfg_fp,
      'input_fingerprint' => inp_fp,
      'actions_fingerprint' => act_fp,
      'ledger_digest' => ledger_digest,
      'generation_max' => fragments.map { |f| f['generation'] }.max || 0
    }
    safe_write(state_path, Canon.dump(state), 'unsafe_output_path')
    safe_write(state_dir.join('kev-ledger.state.json'), Canon.dump(state), 'unsafe_state_path') if state_dir.to_s != out_state_dir.to_s
  rescue RunFailure => e
    if out_dir
      write_error(out_dir, profile_name, e.reason, e.details)
    else
      warn Canon.dump({'schema_version' => 'kev.error.v1', 'profile' => profile_name, 'reason' => e.reason, 'details' => e.details})
    end
    exit 2
  end
end

main
RUBY
chmod +x /app/bin/kev-ledger
