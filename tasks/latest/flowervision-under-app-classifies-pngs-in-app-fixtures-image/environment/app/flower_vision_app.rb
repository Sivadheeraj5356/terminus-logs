# frozen_string_literal: true

require_relative "../config/boot"
require_relative "controllers/api/v1/predict_controller"

class FlowerVisionApp
  def call(env)
    req = Rack::Request.new(env)
    if req.post? && req.path_info == "/api/v1/predict"
      Api::V1::PredictController.new.call(req)
    elsif req.get? && req.path_info == "/health"
      [200, { "content-type" => "application/json" }, [{ ok: true }.to_json]]
    else
      [404, { "content-type" => "application/json" }, [{ error: "not_found" }.to_json]]
    end
  end
end
