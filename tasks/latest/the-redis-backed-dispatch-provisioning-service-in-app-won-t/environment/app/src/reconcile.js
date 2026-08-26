'use strict';

const FIELDS = ['borough', 'zone', 'service_zone'];

/**
 * Decide the target field values for a single dispatch zone.
 *
 * Canonical TLC values win over drifted Redis values; a locked operator override
 * wins over canonical for the fields it names; unlocked overrides are ignored;
 * a LocationID absent from the canonical lookup is left untouched.
 *
 * @param {object} current    Current zone fields: { borough, zone, service_zone }.
 * @param {object|null} canonical  Canonical row, or null if the id is unknown.
 * @param {object|undefined} override  Operator override for this id, or undefined.
 * @returns {{ target: object, appliedLockedOverride: boolean, known: boolean }}
 */
function computeTarget(current, canonical, override) {
  if (!canonical) {
    return {
      target: {
        borough: current.borough,
        zone: current.zone,
        service_zone: current.service_zone,
      },
      appliedLockedOverride: false,
      known: false,
    };
  }

  const target = {
    borough: canonical.borough,
    zone: canonical.zone,
    service_zone: canonical.service_zone,
  };

  let appliedLockedOverride = false;
  if (override && override.locked === true) {
    for (const f of FIELDS) {
      if (Object.prototype.hasOwnProperty.call(override, f)) {
        target[f] = override[f];
      }
    }
    appliedLockedOverride = true;
  }

  return { target, appliedLockedOverride, known: true };
}

module.exports = { computeTarget, FIELDS };
