# frozen_string_literal: true

module F5
  module StubBind
    module_function

    def copy_parent(layer_rows, parent_scale)
      layer_rows.map { |lr| lr.merge('scale_u32' => parent_scale) }
    end
  end
end
