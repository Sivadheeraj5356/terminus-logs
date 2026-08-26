'use strict';

const { splitBlocks } = require('./blocks');

function field(block, key) {
  const match = block.match(new RegExp(`^${key}:\\s*(.+)$`, 'mi'));
  return match ? match[1].trim() : '';
}

function value(block, key) {
  const match = block.match(new RegExp(`^${key}:\\s*(.+)$`, 'mi'));
  return match ? match[1].trim() : undefined;
}

function parseRecords(text) {
  return splitBlocks(text).map((block) => ({
    id: field(block, 'Record'),
    recordedAt: field(block, 'Recorded-At'),
    scope: field(block, 'Scope'),
    state: field(block, 'State'),
    approvals: field(block, 'Approvals').split(',').map((entry) => entry.trim()).filter(Boolean),
    supersedes: field(block, 'Supersedes').split(',').map((entry) => entry.trim()).filter(Boolean),
    delta: {
      debugInferenceEnabled: value(block, 'Debug-Inference'),
      corsAllowedOrigins: value(block, 'CORS-Origins'),
      maxUploadBytes: value(block, 'Max-Upload-Bytes'),
      telemetryRedactionEnabled: value(block, 'Telemetry-Redaction'),
      telemetryRedactedFields: value(block, 'Telemetry-Fields'),
      moderationThresholds: value(block, 'Moderation-Thresholds'),
    },
  }));
}

module.exports = { parseRecords };
