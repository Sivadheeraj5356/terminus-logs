# frozen_string_literal: true

module Api
  module V1
    class PredictController
      def call(req)
        body = JSON.parse(req.body.read)
        image_id = body["image_id"]
        result = InferenceService.predict(image_id: image_id)
        # BUG: wrong response keys / stale mapping
        payload = {
          "prediction" => result["class"],
          "confidence" => result["confidence"],
          "cache_status" => result["cache"]
        }
        [200, { "content-type" => "application/json" }, [payload.to_json]]
      rescue StandardError => e
        [500, { "content-type" => "application/json" }, [{ "error" => e.message }.to_json]]
      end
    end
  end
end
