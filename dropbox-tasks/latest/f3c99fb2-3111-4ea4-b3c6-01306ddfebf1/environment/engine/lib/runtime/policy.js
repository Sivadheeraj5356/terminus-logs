'use strict';

function applyThresholds(decision, policy) {
  const threshold = policy.moderationThresholds[decision.label];
  return { ...decision, flagged: typeof threshold === 'number' && decision.confidence >= threshold };
}

module.exports = { applyThresholds };
