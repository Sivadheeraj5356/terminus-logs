'use strict';

function renderConfig(policy, service) {
  return `'use strict';\n\nconst inferenceConfig = ${JSON.stringify({
    service,
    debugInferenceEnabled: policy.debugInferenceEnabled,
    cors: { origin: policy.corsAllowedOrigins, methods: ['GET', 'POST'], credentials: true },
    corsAllowedOrigins: policy.corsAllowedOrigins,
    maxUploadBytes: policy.maxUploadBytes,
    telemetryRedactionEnabled: policy.telemetryRedactionEnabled,
    telemetryRedactedFields: policy.telemetryRedactedFields,
    telemetry: { endpoint: 'http://telemetry.internal.local/ingest', sampleRate: 1, redactionEnabled: policy.telemetryRedactionEnabled },
    moderationThresholds: policy.moderationThresholds,
  }, null, 2)};\n\nmodule.exports = inferenceConfig;\n`;
}

module.exports = { renderConfig };
