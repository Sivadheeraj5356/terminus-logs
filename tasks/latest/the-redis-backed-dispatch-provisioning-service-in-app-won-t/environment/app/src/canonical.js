'use strict';

const fs = require('fs');
const { parse } = require('csv-parse/sync');

const CANONICAL_CSV = process.env.CANONICAL_CSV || '/app/data/taxi_zone_lookup.csv';

/**
 * Load the canonical NYC TLC taxi-zone lookup table.
 *
 * Returns a Map keyed by integer LocationID whose values are objects of the
 * shape { borough, zone, service_zone }. This is the source of truth that
 * Redis zone hashes are reconciled against.
 */
function loadCanonicalZones(csvPath = CANONICAL_CSV) {
  const raw = fs.readFileSync(csvPath, 'utf8');
  const rows = parse(raw, { columns: true, skip_empty_lines: true, trim: false });
  const byId = new Map();
  for (const row of rows) {
    const id = Number.parseInt(row.LocationID, 10);
    if (!Number.isInteger(id)) continue;
    byId.set(id, {
      borough: row.Borough,
      zone: row.Zone,
      service_zone: row.service_zone,
    });
  }
  return byId;
}

module.exports = { loadCanonicalZones, CANONICAL_CSV };
