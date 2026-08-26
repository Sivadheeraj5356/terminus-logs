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

    def initialize(root:, case_id:, mode_id:)
      @root = root
      @case_id = case_id
      @mode_id = mode_id
    end

    def run!
      rows = []
      replay_tag = F5::ScratchArena.read_tag == 'clean' ? 'live' : 'replay'
      row_set = load_row_set
      stats = Q9::ArmA.arm_a(row_set, { 'mode' => @mode_id })
      global_bounds = global_bounds_for(@mode_id)
      shard = load_shard
      layer_rows = build_layer_rows(shard, stats)
      bound_for = ->(layer_id) {
        ov = shard.dig('layers', layer_id) || {}
        M2::PolicyMux.merge_bounds(global_bounds, ov)
      }
      layer_rows.each do |lr|
        clipped = M2::ClipB.clip_b(lr['tensor_vals'], bound_for.call(lr['layer_id']), lr)
        scale = derive_scale(clipped, @mode_id)
        digest = Util::RowCodec.row_digest(@case_id, @mode_id, lr['layer_id'], scale, stats[:min], stats[:max], replay_tag)
        rows << {
          'case_id' => @case_id,
          'mode_id' => @mode_id,
          'layer_id' => lr['layer_id'],
          'scale_u32' => scale,
          'stat_min' => stats[:min],
          'stat_max' => stats[:max],
          'replay_tag' => replay_tag,
          'row_digest' => digest
        }
      end
      bound = F5::BindC.bind_c(layer_rows, shard, @mode_id)
      rows.zip(bound).map do |row, br|
        row.merge('scale_u32' => br['scale_u32'])
      end.map do |row|
        row['row_digest'] = Util::RowCodec.row_digest(
          row['case_id'], row['mode_id'], row['layer_id'], row['scale_u32'],
          row['stat_min'], row['stat_max'], row['replay_tag']
        )
        row
      end
    end

    def load_row_set
      case @case_id
      when 'sage'
        Util::JsonRead.load_ndjson(File.join(@root, 'h5', 'w1', 'sag_a.ndjson'))
      when 'opal'
        Util::JsonRead.load_ndjson(File.join(@root, 'h5', 'w1', 'opa_b.ndjson'))
      else
        Util::JsonRead.load_ndjson(File.join(@root, 'h5', 'w1', 'sag_a.ndjson'))[0, 3]
      end
    end

    def global_bounds_for(mode_id)
      path = File.join(@root, 'h5', 'x7', 'policy_table.toml')
      table = TOML.load(File.read(path))
      table[mode_id] || table['default'] || { 'lo' => -1.0, 'hi' => 1.0 }
    end

    def load_shard
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

    def derive_scale(clipped, mode_id)
      base = clipped.map { |v| (v * 1000).round }.sum.abs
      case mode_id
      when 'int8_strict' then (base % 2000) + 256
      when 'mixed_edge' then (base % 3000) + 512
      else (base % 1500) + 128
      end
    end
  end
end

require 'toml'
