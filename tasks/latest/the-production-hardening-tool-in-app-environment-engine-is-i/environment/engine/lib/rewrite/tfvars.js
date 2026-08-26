'use strict';

function renderTfvars(policy) {
  const origins = policy.corsAllowedOrigins.map((origin) => JSON.stringify(origin)).join(', ');
  return `debug_inference_enabled = ${policy.debugInferenceEnabled}\n\ncors_allowed_origins = [${origins}]\n\nmax_upload_bytes = ${policy.maxUploadBytes}\n\ntelemetry_redaction_enabled = ${policy.telemetryRedactionEnabled}\n\nmoderation_threshold_safe       = ${policy.moderationThresholds.safe}\nmoderation_threshold_suggestive = ${policy.moderationThresholds.suggestive}\nmoderation_threshold_explicit   = ${policy.moderationThresholds.explicit}\n`;
}

module.exports = { renderTfvars };
