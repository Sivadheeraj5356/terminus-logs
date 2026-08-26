#!/usr/bin/env node
// scripts/seed_db.js
// Seeds the SQLite database with historical flaky-run data.
// Generates deterministic fixture data for the flaky-repro tool.

const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const DB_PATH = path.join(__dirname, '..', 'db', 'history.db');
const DB_DIR = path.dirname(DB_PATH);

async function main() {
  if (!fs.existsSync(DB_DIR)) {
    fs.mkdirSync(DB_DIR, { recursive: true });
  }

  const SQL = await initSqlJs();
  const db = new SQL.Database();

  db.run(`
    CREATE TABLE IF NOT EXISTS test_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      spec_file TEXT NOT NULL,
      browser TEXT NOT NULL,
      status TEXT NOT NULL,
      duration_ms INTEGER NOT NULL,
      retry_attempt INTEGER NOT NULL DEFAULT 0,
      session_id TEXT NOT NULL,
      parent_session_id TEXT,
      deleted INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS browser_projects (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      browser TEXT NOT NULL,
      project_name TEXT NOT NULL,
      worker_count INTEGER NOT NULL DEFAULT 2,
      shard_count INTEGER NOT NULL DEFAULT 1,
      retry_on_failure INTEGER NOT NULL DEFAULT 2,
      cache_key TEXT,
      created_at INTEGER NOT NULL
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS execution_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      spec_file TEXT NOT NULL,
      browser TEXT NOT NULL,
      planned_session_id TEXT NOT NULL,
      status TEXT NOT NULL,
      retry_count INTEGER NOT NULL DEFAULT 0,
      interrupted INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL
    )
  `);

  // Seed test_runs with realistic historical data
  // Includes soft-deleted rows and rerun sessions (parent_session_id set)
  const baseTime = 1700000000;
  const specs = [
    'tests/e2e/checkout.spec.ts',
    'tests/e2e/login.spec.ts',
    'tests/e2e/search.spec.ts',
    'tests/e2e/cart.spec.ts',
    'tests/e2e/profile.spec.ts',
  ];
  const browsers = ['chromium', 'firefox', 'webkit'];

  const sessions = [
    { id: 'sess-001', parent: null, deleted: 0, offset: 0 },
    { id: 'sess-002', parent: null, deleted: 0, offset: 3600 },
    { id: 'sess-003', parent: 'sess-001', deleted: 0, offset: 7200 },
    { id: 'sess-004', parent: null, deleted: 1, offset: 10800 },
    { id: 'sess-005', parent: null, deleted: 0, offset: 14400 },
    { id: 'sess-006', parent: 'sess-002', deleted: 0, offset: 18000 },
  ];

  // Deterministic data per spec+browser combo
  const outcomes = {
    'tests/e2e/checkout.spec.ts:chromium': ['failed', 'failed', 'passed', 'failed', 'passed'],
    'tests/e2e/checkout.spec.ts:firefox': ['passed', 'failed', 'failed', 'passed', 'passed'],
    'tests/e2e/checkout.spec.ts:webkit': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/login.spec.ts:chromium': ['failed', 'passed', 'failed', 'failed', 'failed'],
    'tests/e2e/login.spec.ts:firefox': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/login.spec.ts:webkit': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/search.spec.ts:chromium': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/search.spec.ts:firefox': ['failed', 'passed', 'failed', 'passed', 'passed'],
    'tests/e2e/search.spec.ts:webkit': ['failed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/cart.spec.ts:chromium': ['passed', 'passed', 'failed', 'passed', 'passed'],
    'tests/e2e/cart.spec.ts:firefox': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/cart.spec.ts:webkit': ['failed', 'passed', 'failed', 'passed', 'passed'],
    'tests/e2e/profile.spec.ts:chromium': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/profile.spec.ts:firefox': ['passed', 'passed', 'passed', 'passed', 'passed'],
    'tests/e2e/profile.spec.ts:webkit': ['passed', 'passed', 'passed', 'passed', 'passed'],
  };

  let rowId = 1;
  sessions.forEach((sess, sessIdx) => {
    specs.forEach((spec) => {
      browsers.forEach((browser) => {
        const key = `${spec}:${browser}`;
        const statusList = outcomes[key] || ['passed', 'passed', 'passed', 'passed', 'passed'];
        const status = statusList[sessIdx] || 'passed';
        const duration = 1200 + (rowId * 37) % 4000;
        db.run(
          `INSERT INTO test_runs (spec_file, browser, status, duration_ms, retry_attempt, session_id, parent_session_id, deleted, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          [spec, browser, status, duration, sess.parent ? 1 : 0, sess.id, sess.parent || null, sess.deleted, baseTime + sess.offset + rowId]
        );
        rowId++;
      });
    });
  });

  // Seed browser_projects — multiple rows per browser from cache-key upgrades
  const projectData = [
    ['chromium', 'Desktop Chrome Legacy', 4, 4, 1, 'chrome-v118', baseTime - 86400],
    ['firefox', 'Desktop Firefox', 2, 1, 2, 'ff-v121', baseTime],
    ['webkit', 'Desktop Safari', 1, 1, 2, 'wk-v17', baseTime],
    ['chromium', 'Desktop Chrome', 2, 2, 3, 'chrome-v120', baseTime],
  ];

  projectData.forEach(([browser, name, workers, shards, retries, cacheKey, ts]) => {
    db.run(
      `INSERT INTO browser_projects (browser, project_name, worker_count, shard_count, retry_on_failure, cache_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [browser, name, workers, shards, retries, cacheKey, ts]
    );
  });

  // Seed execution_results with some stale/interrupted data
  const execData = [
    ['tests/e2e/checkout.spec.ts', 'chromium', 'plan-sess-alpha', 'passed', 2, 0, baseTime + 1000],
    ['tests/e2e/login.spec.ts', 'chromium', 'plan-sess-alpha', 'failed', 3, 0, baseTime + 1001],
    ['tests/e2e/search.spec.ts', 'webkit', 'plan-sess-alpha', 'failed', 2, 0, baseTime + 1002],
    ['tests/e2e/search.spec.ts', 'firefox', 'plan-sess-alpha', 'failed', 1, 1, baseTime + 1003],
    ['tests/e2e/cart.spec.ts', 'chromium', 'plan-sess-old', 'failed', 1, 0, baseTime + 500],
  ];

  execData.forEach(([spec, browser, planSess, status, retries, interrupted, ts]) => {
    db.run(
      `INSERT INTO execution_results (spec_file, browser, planned_session_id, status, retry_count, interrupted, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [spec, browser, planSess, status, retries, interrupted, ts]
    );
  });

  // Write DB to disk
  const data = db.export();
  const buffer = Buffer.from(data);
  fs.writeFileSync(DB_PATH, buffer);

  console.log(`Database seeded at ${DB_PATH}`);
  console.log(`  test_runs: ${db.exec('SELECT COUNT(*) FROM test_runs')[0].values[0][0]} rows`);
  console.log(`  browser_projects: ${db.exec('SELECT COUNT(*) FROM browser_projects')[0].values[0][0]} rows`);
  console.log(`  execution_results: ${db.exec('SELECT COUNT(*) FROM execution_results')[0].values[0][0]} rows`);
  db.close();
}

main().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
