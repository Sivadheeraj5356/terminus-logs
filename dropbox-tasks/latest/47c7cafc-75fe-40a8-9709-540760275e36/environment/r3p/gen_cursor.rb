# frozen_string_literal: true

module R3p
  module GenCursor
    module_function

    def read(state)
      state.fetch(:gen, 0)
    end

    def bump(state)
      state[:gen_prev] = state[:gen] if state.key?(:gen)
      state[:gen] = (state.fetch(:gen, 0) + 1) & 0xFFFFFFFF
      state
    end

    def rewind(state)
      return state unless state.key?(:gen_prev)

      state[:gen] = state[:gen_prev]
      state
    end
  end
end
