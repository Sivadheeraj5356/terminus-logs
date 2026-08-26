// lib/reportSnapshot.js
// Legacy report snapshot helper from the v2.0 reporting experiment.
// Not wired into the current CLI path; kept for reference during cleanup.

const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const DB_PATH = path.join(__dirname, '..', 'db', 'history.db');

async function loadDb() {
  const SQL = await initSqlJs();
  const fileBuffer = fs.readFileSync(DB_PATH);
  return new SQL.Database(fileBuffer);
}

async function buildSnapshot() {
  const db = await loadDb();
  const results = db.exec(`
    SELECT spec_file, browser, status
    FROM test_runs
    ORDER BY spec_file ASC
  `);
  db.close();
  return results;
}

module.exports = { buildSnapshot };
