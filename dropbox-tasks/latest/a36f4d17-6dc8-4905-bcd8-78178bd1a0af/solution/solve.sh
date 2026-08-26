#!/usr/bin/env bash
set -euo pipefail
cd /app

cat > environment/q9/arm_a.rb <<'RUBY'
# frozen_string_literal: true

module Q9
  module ArmA
    module_function

    def default_bounds(mode_id)
      case mode_id
      when 'int8_strict' then { 'lo' => -0.5, 'hi' => 0.5 }
      when 'mixed_edge' then { 'lo' => -0.6, 'hi' => 0.6 }
      when 'fp16_baseline' then { 'lo' => -1.0, 'hi' => 1.0 }
      else { 'lo' => -0.75, 'hi' => 0.75 }
      end
    end

    def arm_a(row_set, mode_map)
      vals = row_set.flat_map { |row| Array(row['vals']) }.map(&:to_f)
      return { min: 0.0, max: 0.0 } if vals.empty?

      mode_id = mode_map.fetch('mode')
      bounds = mode_map.fetch('bounds', default_bounds(mode_id))
      lo = bounds.fetch('lo').to_f
      hi = bounds.fetch('hi').to_f
      clipped = vals.map do |v|
        x = v
        x = hi if x > hi
        x = lo if x < lo
        x
      end
      { min: clipped.min, max: clipped.max }
    end
  end
end
RUBY

cat > environment/m2/clip_b.rb <<'RUBY'
# frozen_string_literal: true

module M2
  module ClipB
    module_function

    def clip_b(tensor_vals, bound_table, _layer_ctx)
      lo = bound_table.fetch('lo', -1.0).to_f
      hi = bound_table.fetch('hi', 1.0).to_f
      tensor_vals.map do |v|
        x = v.to_f
        x = hi if x > hi
        x = lo if x < lo
        x.round(3)
      end
    end
  end
end
RUBY

cat > environment/f5/bind_c.rb <<'RUBY'
# frozen_string_literal: true

module F5
  module BindC
    module_function

    def bind_c(layer_rows, _shard_map, mode_id)
      layer_rows.map do |lr|
        vals = Array(lr['tensor_vals']).map(&:to_f)
        lo = lr.fetch('bound_lo', -1.0).to_f
        hi = lr.fetch('bound_hi', 1.0).to_f
        clipped = vals.map do |v|
          x = v
          x = hi if x > hi
          x = lo if x < lo
          x.round(3)
        end
        base = clipped.map { |v| (v * 1000).round }.sum.abs
        offset = lr['layer_id'].bytes.sum
        scale = case mode_id
                when 'int8_strict' then (base % 2000) + 256 + offset
                when 'mixed_edge' then (base % 3000) + 512 + (offset * 2)
                when 'fp16_baseline' then (base % 1500) + 128 + offset
                else (base % 2500) + 384 + (offset * 3)
                end
        lr.merge('scale_u32' => scale)
      end
    end
  end
end
RUBY

cat > environment/engine/wave_runner.rb <<'RUBY'
# frozen_string_literal: true

require_relative 'pipeline'

module Engine
  module WaveRunner
    module_function

    def run_case(root, case_id, modes: Engine::Pipeline::PROFILE_BANDS, source_path: nil, shard_path: nil)
      modes.flat_map do |mode_id|
        Engine::Pipeline.new(
          root: root,
          case_id: case_id,
          mode_id: mode_id,
          source_path: source_path,
          shard_path: shard_path
        ).run!
      end
    end
  end
end
RUBY

cat > environment/engine/pipeline.rb <<'RUBY'
# frozen_string_literal: true

require_relative '../q9/arm_a'
require_relative '../m2/clip_b'
require_relative '../m2/policy_mux'
require_relative '../f5/bind_c'
require_relative '../f5/scratch_arena'
require_relative '../util/row_codec'
require_relative '../util/json_read'

module Engine
  class Pipeline
    PROFILE_BANDS = %w[fp16_baseline int8_strict mixed_edge].freeze

    def initialize(root:, case_id:, mode_id:, source_path: nil, shard_path: nil)
      @root = root
      @case_id = case_id
      @mode_id = mode_id
      @source_path = source_path
      @shard_path = shard_path
    end

    def run!
      replay_tag = F5::ScratchArena.read_tag == 'clean' ? 'live' : 'replay'
      row_set = load_row_set
      mode_bounds = global_bounds_for(@mode_id)
      stats = Q9::ArmA.arm_a(row_set, { 'mode' => @mode_id, 'bounds' => mode_bounds })
      shard = load_shard
      layer_rows = build_layer_rows(shard, stats)
      bound_layers = layer_rows.map do |lr|
        bounds = M2::PolicyMux.merge_bounds(mode_bounds, shard.dig('layers', lr['layer_id']))
        lr.merge('bound_lo' => bounds['lo'], 'bound_hi' => bounds['hi'])
      end
      clipped_layers = bound_layers.map do |lr|
        clipped = M2::ClipB.clip_b(lr['tensor_vals'], { 'lo' => lr['bound_lo'], 'hi' => lr['bound_hi'] }, lr)
        lr.merge('tensor_vals' => clipped)
      end
      F5::BindC.bind_c(clipped_layers, shard, @mode_id).map do |lr|
        digest = Util::RowCodec.row_digest(
          @case_id, @mode_id, lr['layer_id'], lr['scale_u32'],
          stats[:min], stats[:max], replay_tag
        )
        {
          'case_id' => @case_id,
          'mode_id' => @mode_id,
          'layer_id' => lr['layer_id'],
          'scale_u32' => lr['scale_u32'],
          'stat_min' => stats[:min],
          'stat_max' => stats[:max],
          'replay_tag' => replay_tag,
          'row_digest' => digest
        }
      end
    end

    def global_bounds_for(mode_id)
      path = File.join(@root, 'h5', 'x7', 'policy_table.toml')
      table = TOML.load(File.read(path))
      table[mode_id] || table['default'] || { 'lo' => -1.0, 'hi' => 1.0 }
    end

    def load_row_set
      if @source_path
        return Util::JsonRead.load_ndjson(abs_env_path(@source_path))
      end
      case @case_id
      when 'sage'
        Util::JsonRead.load_ndjson(File.join(@root, 'h5', 'w1', 'sag_a.ndjson'))
      when 'opal'
        Util::JsonRead.load_ndjson(File.join(@root, 'h5', 'w1', 'opa_b.ndjson'))
      else
        Util::JsonRead.load_ndjson(File.join(@root, 'h5', 'w1', 'sag_a.ndjson'))[0, 3]
      end
    end

    def load_shard
      if @shard_path
        return TOML.load(File.read(abs_env_path(@shard_path)))
      end
      path = case @case_id
             when 'birch' then File.join(@root, 'h5', 'w2', 'shard_birch.toml')
             when 'rowan' then File.join(@root, 'h5', 'w2', 'shard_rowan.toml')
             else File.join(@root, 'h5', 'w2', 'shard_birch.toml')
             end
      TOML.load(File.read(path))
    end

    def build_layer_rows(shard, stats)
      layers = shard.fetch('layers', {})
      layers.keys.sort.map do |lid|
        {
          'layer_id' => lid,
          'tensor_vals' => [stats[:min], stats[:max], (stats[:min] + stats[:max]) / 2.0]
        }
      end
    end

    def abs_env_path(path)
      File.expand_path(path, @root)
    end
  end
end

require 'toml'
RUBY

cat > environment/qcl/drive_qcl.rb <<'RUBY'
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

STOCK_MODES = Engine::Pipeline::PROFILE_BANDS

def pool_modes(spec)
  if spec['modes']
    Array(spec['modes']).map(&:to_s)
  elsif spec['mode_hint']
    [spec['mode_hint'].to_s]
  else
    STOCK_MODES
  end
end

def main
  matrix_all = ARGV.include?('--matrix-all')
  abort('usage: drive_qcl.rb --matrix-all') unless matrix_all

  FileUtils.mkdir_p('/app/output')
  case_ids = File.readlines(File.join(ROOT, 'docs', 'case_ids.txt')).map(&:strip).reject(&:empty?)
  rows = []
  case_ids.each do |cid|
    rows.concat(Engine::WaveRunner.run_case(ROOT, cid, modes: STOCK_MODES))
  end
  Dir.glob(File.join(ROOT, 'h5', 'pool', 'QZ-*.json')).sort.each do |path|
    spec = JSON.parse(File.read(path))
    rows.concat(
      Engine::WaveRunner.run_case(
        ROOT,
        spec.fetch('case_id'),
        modes: pool_modes(spec),
        source_path: spec['source'],
        shard_path: spec['shard']
      )
    )
  end
  emit = {
    'meta' => { 'matrix' => 'all', 'rows_total' => rows.length },
    'rows' => rows
  }
  File.write('/app/output/qcl_emit.json', JSON.pretty_generate(emit))
end

main if $PROGRAM_NAME == __FILE__
RUBY

ruby environment/qcl/drive_qcl.rb --matrix-all
