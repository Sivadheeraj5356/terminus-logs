# frozen_string_literal: true

require 'toml'

module M2
  module PolicyMux
    module_function

    def merge_bounds(global_table, layer_override)
      base = global_table.dup
      return base unless layer_override

      if layer_override['lo']
        base['lo'] = layer_override['lo']
      end
      if layer_override['hi']
        base['hi'] = layer_override['hi']
      end
      base
    end

    def load_global(path)
      text = File.read(path)
      table = TOML.load(text)
      table['default'] || { 'lo' => -1.0, 'hi' => 1.0 }
    end
  end
end
