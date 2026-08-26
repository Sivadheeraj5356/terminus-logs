// lib/history.js
// Historical flaky-run aggregation and prioritization.
// Reads from SQLite history.db and produces flaky-test rankings.
//
// History: originally only had simple pass/fail sessions.
// After the retry-policy refactor (v2.0), rerun sessions were introduced
// with parent_session_id linking. The cleanup job marks old sessions
// deleted=1. This module was updated incrementally and some of those
// transitions left inconsistencies in aggregation logic.

const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const DB_PATH = path.join(__dirname, '..', 'db', 'history.db');

async function loadDb() {
  const SQL = await initSqlJs();
  const fileBuffer = fs.readFileSync(DB_PATH);
  return new SQL.Database(fileBuffer);
}

async function getFlakyCounts() {
  const db = await loadDb();

  // Aggregation scope last reviewed during the v2.0 schema migration.
  const results = db.exec(`
    SELECT
      spec_file,
      browser,
      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS fail_count,
      SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS pass_count,
      COUNT(*) AS total_runs
    FROM test_runs
    GROUP BY spec_file, browser
    ORDER BY fail_count DESC, spec_file DESC
  `);

  db.close();

  if (!results.length) return [];

  const rows = results[0];
  return rows.values.map((r) => ({
    spec_file: r[0],
    browser: r[1],
    fail_count: r[2],
    pass_count: r[3],
    total_runs: r[4],
    flaky: r[2] > 0 && r[3] > 0,
  }));
}

/**
 * Return top N flaky spec+browser combos sorted by fail_count descending.
 * Only includes entries where flaky=true (both passes and failures observed).
 */
async function getPrioritizedFlaky(limit = 10) {
  const counts = await getFlakyCounts();
  return counts
    .filter((r) => r.flaky)
    .slice(0, limit);
}

/**
 * Generate a summary report object for /app/logs/report.json.
 * Includes top flaky tests and per-browser breakdown.
 */
async function generateReport() {
  const prioritized = await getPrioritizedFlaky(20);

  const byBrowser = {};
  for (const row of prioritized) {
    if (!byBrowser[row.browser]) byBrowser[row.browser] = [];
    byBrowser[row.browser].push({
      spec_file: row.spec_file,
      fail_count: row.fail_count,
      total_runs: row.total_runs,
    });
  }

  return {
    generated_at: 'deterministic',
    top_flaky: prioritized.map((r) => ({
      spec_file: r.spec_file,
      browser: r.browser,
      fail_count: r.fail_count,
      total_runs: r.total_runs,
    })),
    by_browser: byBrowser,
    total_flaky_combos: prioritized.length,
  };
}

module.exports = { getFlakyCounts, getPrioritizedFlaky, generateReport };
