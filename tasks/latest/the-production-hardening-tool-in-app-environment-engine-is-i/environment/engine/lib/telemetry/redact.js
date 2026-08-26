'use strict';

function redactTelemetry(request, fields) {
  const copy = JSON.parse(JSON.stringify(request));
  for (const dottedPath of fields) {
    const parts = dottedPath.split('.');
    let target = copy;
    for (const part of parts.slice(0, -1)) target = target && target[part];
    if (target && Object.prototype.hasOwnProperty.call(target, parts.at(-1))) target[parts.at(-1)] = '[REDACTED]';
  }
  return copy;
}

module.exports = { redactTelemetry };
