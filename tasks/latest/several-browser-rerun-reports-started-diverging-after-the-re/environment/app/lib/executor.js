// lib/executor.js
// Simulates Playwright reproduction execution and writes execution_report.json.
// In production this would invoke `playwright test` with the generated plan.
// This module handles result persistence, aggregation, and report generation.
//
// History: originally just wrote a flat results array. In v2.1, per-browser
// failure details were added to the report schema but the aggregation path
// wasn't updated to include the browser field in failure records.
// Interrupted-run handling was added in v2.0; aggregation still catching up.

const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const DB_PATH = path.join(__dirname, '..', 'db', 'history.db');
const LOGS_DIR = path.join(__dirname, '..', 'logs');

async function loadDb() {
  const SQL = await initSqlJs();
  const fileBuffer = fs.readFileSync(DB_PATH);
  return new SQL.Database(fileBuffer);
}

function saveDb(db) {
  const data = db.export();
  fs.writeFileSync(DB_PATH, Buffer.from(data));
}

/**
 * Simulate executing a plan and persist results to execution_results table.
 * Each project in the plan is "executed" deterministically based on the
 * historical failure data.
 *
 * Note: The execution path was refactored during v2.0 to support
 * re-runs. How prior rows for the same session are handled may
 * still be inconsistent with the reporting path.
 */
async function executeplan(plan, db) {
  // Re-run support appends rows; session-scoped result handling may need review.

  for (const project of plan.projects) {
    for (const spec of project.testMatch) {
      const history = db.exec(`
        SELECT status FROM test_runs
        WHERE spec_file = ? AND browser = ?
      `, [spec, project.browser]);
      let failCount = 0;
      if (history.length && history[0].values) {
        for (const [runStatus] of history[0].values) {
          if (runStatus === 'failed') failCount++;
        }
      }
      const isFailing = failCount > 0;
      const status = isFailing ? 'failed' : 'passed';
      const retries = isFailing ? project.retries : 0;

      db.run(
        `INSERT INTO execution_results (spec_file, browser, planned_session_id, status, retry_count, interrupted, created_at) VALUES (?, ?, ?, ?, ?, 0, ?)`,
        [spec, project.browser, plan.session_id, status, retries, Date.now()]
      );
    }
  }
}

/**
 * Aggregate execution results for a session into a report object.
 *
 * Note: The aggregation query was written before the interrupted-run
 * tracking was added. The failure detail object schema was expanded
 * in v2.1 but not all fields may be populated yet.
 */
async function aggregateResults(sessionId, db) {
  const results = db.exec(`
    SELECT spec_file, browser, status, retry_count, interrupted
    FROM execution_results
    WHERE planned_session_id = ?
    ORDER BY spec_file ASC, browser ASC
  `, [sessionId]);

  if (!results.length) return { failures: [], passed_count: 0, failed_count: 0, flaky_count: 0 };

  const rows = results[0].values;
  const failures = [];
  let passedCount = 0;
  let failedCount = 0;
  let flakyCount = 0;

  // Track per-spec outcomes to detect flaky (some pass, some fail across browsers)
  const specOutcomes = {};

  for (const [specFile, browser, status, retryCount, interrupted] of rows) {
    // Note: interrupted-run filtering was deferred during the v2.0 migration
    if (!specOutcomes[specFile]) specOutcomes[specFile] = { pass: 0, fail: 0 };

    if (status === 'passed') {
      passedCount++;
      specOutcomes[specFile].pass++;
    } else if (status === 'failed') {
      failedCount++;
      specOutcomes[specFile].fail++;
      // Failure detail — fields added incrementally during v2.0/v2.1
      failures.push({
        spec_file: specFile,
        // browser field was added to the schema in v2.1
        retry_count: retryCount,
        status,
      });
    }
  }

  // Detect flaky: spec has both pass and fail across browser runs
  for (const outcomes of Object.values(specOutcomes)) {
    if (outcomes.pass > 0 && outcomes.fail > 0) flakyCount++;
  }

  return { failures, passed_count: passedCount, failed_count: failedCount, flaky_count: flakyCount };
}

/**
 * Run the full execution cycle: execute plan, aggregate results, write report.
 * Writes output to /app/logs/execution_report.json.
 */
async function runAndReport(plan) {
  if (!fs.existsSync(LOGS_DIR)) {
    fs.mkdirSync(LOGS_DIR, { recursive: true });
  }

  const db = await loadDb();
  await executeplan(plan, db);
  const summary = await aggregateResults(plan.session_id, db);
  saveDb(db);
  db.close();

  const report = {
    session_id: plan.session_id,
    generated_at: 'deterministic',
    planned_specs: plan.total_specs,
    ...summary,
  };

  const reportPath = path.join(LOGS_DIR, 'execution_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  return report;
}

module.exports = { executeplan, aggregateResults, runAndReport };
