#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'fileutils'

ROOT = File.expand_path('..', __dir__)
ENV['RUBYLIB'] = [
  ROOT,
  File.join(ROOT, 'qcl'),
  File.join(ROOT, 'q9'),
  File.join(ROOT, 'm2'),
  File.join(ROOT, 'f5'),
  File.join(ROOT, 'engine'),
  File.join(ROOT, 'util'),
  File.join(ROOT, 'tools')
].join(':')

require_relative '../engine/wave_runner'
require_relative '../util/json_read'

def main
  matrix_all = ARGV.include?('--matrix-all')
  abort('usage: drive_qcl.rb --matrix-all') unless matrix_all

  FileUtils.mkdir_p('/app/output')
  case_ids = File.readlines(File.join(ROOT, 'docs', 'case_ids.txt')).map(&:strip).reject(&:empty?)
  rows = []
  case_ids.each do |cid|
    rows.concat(Engine::WaveRunner.run_case(ROOT, cid))
  end
  Dir.glob(File.join(ROOT, 'h5', 'pool', 'QZ-*.json')).sort.each do |path|
    spec = JSON.parse(File.read(path))
    rows.concat(Engine::WaveRunner.run_case(ROOT, spec.fetch('case_id')))
  end
  emit = {
    'meta' => { 'matrix' => 'all', 'rows_total' => rows.length },
    'rows' => rows
  }
  File.write('/app/output/qcl_emit.json', JSON.pretty_generate(emit))
end

main if $PROGRAM_NAME == __FILE__
