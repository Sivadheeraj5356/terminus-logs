# frozen_string_literal: true

module M7k
  module StepBuf
    module_function

    def buffer_event(step_ix, payload)
      { step: step_ix, bytes: payload.to_s.bytesize }
    end
  end
end
