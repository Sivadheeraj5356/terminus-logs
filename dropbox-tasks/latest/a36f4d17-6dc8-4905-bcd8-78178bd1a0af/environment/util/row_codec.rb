# frozen_string_literal: true

require 'digest'

module Util
  module RowCodec
    module_function

    def canonical_bytes(case_id, mode_id, layer_id, scale_u32, stat_min, stat_max, replay_tag)
      [case_id, mode_id, layer_id, scale_u32.to_s, format('%.6f', stat_min.to_f),
       format('%.6f', stat_max.to_f), replay_tag].join('|')
    end

    def row_digest(case_id, mode_id, layer_id, scale_u32, stat_min, stat_max, replay_tag)
      Digest::SHA256.hexdigest(canonical_bytes(case_id, mode_id, layer_id, scale_u32, stat_min, stat_max, replay_tag))[0, 16]
    end

    def slice_header_layout
      { channel_axis: 1, batch_axis: 0 }
    end
  end
end
