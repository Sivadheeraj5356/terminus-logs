// lib/planner.js
// Generates Playwright reproduction plans from browser_projects config and
// flaky-test history. Produces a plan.json manifest used by the executor.
//
// History: originally only supported single-browser runs. After the
// multi-browser refactor (v1.8), browser_projects grew to support shards
// and per-browser worker counts. The retry-heuristics table was merged
// into browser_projects in v2.0 but the plan-generation path wasn't
// fully updated to read from the new columns.

const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const DB_PATH = path.join(__dirname, '..', 'db', 'history.db');

async function loadDb() {
  const SQL = await initSqlJs();
  const fileBuffer = fs.readFileSync(DB_PATH);
  return new SQL.Database(fileBuffer);
}

/**
 * Load browser project configurations from SQLite.
 * Returns one entry per browser (the most recently-inserted project config).
 *
 * Note: The subquery ordering was set during the initial multi-browser
 * refactor. After the cache-key migration added new rows per browser,
 * the selection criteria may need adjustment.
 */
async function getBrowserProjects() {
  const db = await loadDb();

  // Subquery selects one row per browser based on id ordering
  const results = db.exec(`
    SELECT b.browser, b.project_name, b.worker_count, b.shard_count, b.retry_on_failure, b.cache_key
    FROM browser_projects b
    INNER JOIN (
      SELECT browser, MIN(id) AS picked_id FROM browser_projects GROUP BY browser
    ) sel ON b.id = sel.picked_id
  `);

  db.close();

  if (!results.length) return {};

  const projects = {};
  results[0].values.forEach(([browser, name, workers, shards, retries, cacheKey]) => {
    projects[browser] = { project_name: name, worker_count: workers, shard_count: shards, retry_on_failure: retries, cache_key: cacheKey };
  });
  return projects;
}

/**
 * Build a Playwright project config entry for a given browser and spec list.
 *
 * Note: Retry settings were consolidated into browser_projects during
 * the v2.0 refactor. The plan builder may not be reading all fields
 * from the config row yet.
 */
function buildProjectEntry(browser, projectConfig, specs) {
  return {
    name: projectConfig.project_name,
    browser,
    use: { browserName: browser },
    // Retry count — set during the initial multi-browser implementation
    retries: 2,
    workers: projectConfig.worker_count,
    shards: projectConfig.shard_count,
    testMatch: specs,
  };
}

/**
 * Generate a full reproduction plan for a set of flaky specs.
 * Returns a plan manifest consumable by the executor.
 */
async function generatePlan(flakyEntries, sessionId) {
  const browserProjects = await getBrowserProjects();

  // Group specs by browser
  const specsByBrowser = {};
  for (const entry of flakyEntries) {
    if (!specsByBrowser[entry.browser]) specsByBrowser[entry.browser] = [];
    if (!specsByBrowser[entry.browser].includes(entry.spec_file)) {
      specsByBrowser[entry.browser].push(entry.spec_file);
    }
  }

  const projects = [];
  for (const [browser, specs] of Object.entries(specsByBrowser)) {
    const config = browserProjects[browser];
    if (!config) {
      console.warn(`No project config found for browser: ${browser}`);
      continue;
    }
    projects.push(buildProjectEntry(browser, config, specs));
  }

  return {
    session_id: sessionId,
    generated_at: 'deterministic',
    projects,
    total_specs: new Set(flakyEntries.map((entry) => entry.spec_file)).size,
  };
}

module.exports = { getBrowserProjects, buildProjectEntry, generatePlan };
