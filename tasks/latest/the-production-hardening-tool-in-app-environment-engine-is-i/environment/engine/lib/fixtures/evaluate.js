'use strict';

const path = require('path');
const { evaluateFixture } = require('../helpers');
const { applyThresholds } = require('../runtime/policy');

async function evaluateFixtures(fixtures, fixtureDir, policy, repoRoot) {
  const decisions = [];
  for (const fixture of fixtures) {
    const decision = await evaluateFixture(path.join(fixtureDir, fixture.file), repoRoot);
    decisions.push({ id: fixture.id, file: fixture.file, ...applyThresholds(decision, policy) });
  }
  return decisions;
}

module.exports = { evaluateFixtures };
