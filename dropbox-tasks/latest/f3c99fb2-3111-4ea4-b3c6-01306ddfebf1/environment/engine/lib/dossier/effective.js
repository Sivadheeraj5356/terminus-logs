'use strict';

function parseBoolean(value) { return value === 'true'; }
function parseList(value) { return value ? value.split(',').map((entry) => entry.trim()).filter(Boolean) : undefined; }
function parseThresholds(value) {
  if (!value) return undefined;
  return Object.fromEntries(value.split(',').map((pair) => pair.trim().split('=').map((part) => part.trim())).map(([key, number]) => [key, Number(number)]));
}

function resolveEffectivePolicy(records) {
  const policy = {};
  for (const record of records) {
    if (record.state !== 'ratified') continue;
    const delta = record.delta;
    if (delta.debugInferenceEnabled !== undefined) policy.debugInferenceEnabled = parseBoolean(delta.debugInferenceEnabled);
    if (delta.corsAllowedOrigins) policy.corsAllowedOrigins = parseList(delta.corsAllowedOrigins);
    if (delta.maxUploadBytes) policy.maxUploadBytes = Number(delta.maxUploadBytes);
    if (delta.telemetryRedactionEnabled !== undefined) policy.telemetryRedactionEnabled = parseBoolean(delta.telemetryRedactionEnabled);
    if (delta.telemetryRedactedFields) policy.telemetryRedactedFields = parseList(delta.telemetryRedactedFields);
    if (delta.moderationThresholds) policy.moderationThresholds = parseThresholds(delta.moderationThresholds);
  }
  const needed = ['debugInferenceEnabled', 'corsAllowedOrigins', 'maxUploadBytes', 'telemetryRedactionEnabled', 'telemetryRedactedFields', 'moderationThresholds'];
  if (needed.some((key) => policy[key] === undefined)) throw new Error('dossier does not resolve a complete policy');
  return policy;
}

module.exports = { resolveEffectivePolicy };
