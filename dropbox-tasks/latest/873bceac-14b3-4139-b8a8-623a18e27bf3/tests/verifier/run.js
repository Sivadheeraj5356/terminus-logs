// Authoritative RelicMaze verifier.
// Compiles the agent's Java library, resolves every scenario in /tests/fixtures
// (curated + randomized battery) in a single JVM via BatchRunner, and compares
// each response byte-for-byte against the golden files in /tests/golden. Writes a
// per-scenario report to /tmp/relicmaze_results.json. Node 12 compatible.
'use strict';

const fs = require('fs');
const path = require('path');
const cp = require('child_process');

const SRC = '/app/relicmaze/src/main/java';
const LIB = '/app/relicmaze/lib/postgresql.jar:/app/relicmaze/lib/json.jar';
const BUILD = '/tmp/rm_build_tests';
const OUT = '/tmp/rm_out_tests';
const FIX = '/tests/fixtures';
const GOLD = '/tests/golden';
const RESULTS = '/tmp/relicmaze_results.json';

function rmrf(dir) {
  if (!fs.existsSync(dir)) return;
  if (fs.rmSync) {
    fs.rmSync(dir, { recursive: true, force: true });
  } else {
    fs.rmdirSync(dir, { recursive: true });
  }
}

function walk(dir) {
  let out = [];
  for (const entry of fs.readdirSync(dir)) {
    const p = path.join(dir, entry);
    if (fs.statSync(p).isDirectory()) {
      out = out.concat(walk(p));
    } else if (p.endsWith('.java')) {
      out.push(p);
    }
  }
  return out;
}

function rstrip(s) {
  return s.replace(/[\s\xA0]+$/g, '');
}

function scenarios() {
  return fs.readdirSync(FIX)
    .filter((f) => f.endsWith('.json'))
    .map((f) => f.slice(0, -5))
    .sort();
}

function main() {
  const results = {};
  const names = scenarios();

  let compileError = null;
  try {
    rmrf(BUILD);
    fs.mkdirSync(BUILD, { recursive: true });
    cp.execFileSync('javac', ['-cp', LIB, '-d', BUILD].concat(walk(SRC)), { stdio: 'pipe' });
  } catch (e) {
    compileError = (e.stderr ? e.stderr.toString() : '') + (e.stdout ? e.stdout.toString() : '') || String(e);
  }

  let batchError = null;
  if (!compileError) {
    try {
      rmrf(OUT);
      fs.mkdirSync(OUT, { recursive: true });
      cp.execFileSync('java', ['-cp', BUILD + ':' + LIB, 'com.relicmaze.BatchRunner', FIX, OUT],
        { stdio: 'pipe' });
    } catch (e) {
      batchError = (e.stderr ? e.stderr.toString() : '') + (e.stdout ? e.stdout.toString() : '') || String(e);
    }
  }

  for (const name of names) {
    if (compileError) {
      results[name] = { pass: false, error: 'compile failed:\n' + compileError, expected: null, actual: null };
      continue;
    }
    let expected = null;
    try {
      expected = rstrip(fs.readFileSync(path.join(GOLD, name + '.txt'), 'utf8'));
    } catch (e) {
      results[name] = { pass: false, error: 'missing golden: ' + name, expected: null, actual: null };
      continue;
    }
    let actual = null;
    try {
      actual = rstrip(fs.readFileSync(path.join(OUT, name + '.txt'), 'utf8'));
    } catch (e) {
      results[name] = { pass: false, error: 'no output produced' + (batchError ? ':\n' + batchError : ''),
        expected: expected, actual: null };
      continue;
    }
    results[name] = { pass: actual === expected, expected: expected, actual: actual, error: null };
  }

  fs.writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  const passed = names.filter((n) => results[n].pass).length;
  console.log('relicmaze verifier: ' + passed + '/' + names.length + ' scenarios passed');
  process.exit(passed === names.length ? 0 : 1);
}

main();
