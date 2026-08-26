# frozen_string_literal: true

require_relative 'stub_bind'

module F5
  module BindC
    module_function

    def bind_c(layer_rows, shard_map, mode_id)
      parent = shard_map.fetch('parent_scale', 1024)
      F5::StubBind.copy_parent(layer_rows, parent)
    end
  end
end
