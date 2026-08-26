'use strict';

const inferenceConfig = {
  service: {
    name: 'media-moderation-api',
    port: 3000,
    modelPath: 'model/model.json',
    labels: ['safe', 'suggestive', 'explicit'],
  },
  debugInferenceEnabled: true,
  cors: { origin: '*', methods: ['GET', 'POST'], credentials: true },
  corsAllowedOrigins: ['*'],
  maxUploadBytes: 104857600,
  telemetryRedactionEnabled: false,
  telemetryRedactedFields: [],
  telemetry: {
    endpoint: 'http://telemetry.internal.local/ingest',
    sampleRate: 1,
    redactionEnabled: false,
  },
  moderationThresholds: { safe: 0.15, suggestive: 0.35, explicit: 0.4 },
};

module.exports = inferenceConfig;
