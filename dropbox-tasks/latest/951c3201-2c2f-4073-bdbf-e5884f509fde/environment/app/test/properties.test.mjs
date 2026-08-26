// Property tests for the reconciliation decision function. These exercise the
// pure computeTarget policy (no Redis required) and are a starting point for
// checking your implementation: `npm test`.
import test from 'node:test';
import assert from 'node:assert/strict';
import fc from 'fast-check';

import { computeTarget, FIELDS } from '../src/reconcile.js';

const arbFields = fc.record({
  borough: fc.string(),
  zone: fc.string(),
  service_zone: fc.string(),
});

test('idempotent: reconciling an already-reconciled zone yields no change', () => {
  fc.assert(
    fc.property(arbFields, arbFields, (current, canonical) => {
      const first = computeTarget(current, canonical, undefined);
      const second = computeTarget(first.target, canonical, undefined);
      for (const f of FIELDS) assert.equal(second.target[f], first.target[f]);
    }),
  );
});

test('unlocked overrides never affect the target', () => {
  fc.assert(
    fc.property(arbFields, arbFields, fc.string(), (current, canonical, val) => {
      const withOverride = computeTarget(current, canonical, { zone: val, locked: false });
      const without = computeTarget(current, canonical, undefined);
      for (const f of FIELDS) assert.equal(withOverride.target[f], without.target[f]);
    }),
  );
});

test('unknown zones (no canonical row) are left untouched', () => {
  fc.assert(
    fc.property(arbFields, (current) => {
      const { target, known } = computeTarget(current, null, undefined);
      assert.equal(known, false);
      for (const f of FIELDS) assert.equal(target[f], current[f]);
    }),
  );
});
