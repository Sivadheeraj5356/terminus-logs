'use strict';

function terraformDefaults(policy) {
  return {
    debug_inference_enabled: policy.debugInferenceEnabled,
    cors_allowed_origins: policy.corsAllowedOrigins,
    max_upload_bytes: policy.maxUploadBytes,
    telemetry_redaction_enabled: policy.telemetryRedactionEnabled,
    telemetry_redacted_fields: policy.telemetryRedactedFields,
    moderation_threshold_safe: policy.moderationThresholds.safe,
    moderation_threshold_suggestive: policy.moderationThresholds.suggestive,
    moderation_threshold_explicit: policy.moderationThresholds.explicit,
  };
}

module.exports = { terraformDefaults };
