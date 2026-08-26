// Public RelicMaze self-test verifier.
// Compiles the Java library and checks the sample scenarios in ../fixtures
// against the golden files in ./golden, running them in one JVM via BatchRunner.
// The hidden grading suite covers many more scenarios (including a randomized
// battery), so passing this is necessary but not sufficient. Node 12 compatible.
'use strict';

const fs = require('fs');
const path = require('path');
const cp = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'src/main/java');
const LIB = path.join(ROOT, 'lib/postgresql.jar') + ':' + path.join(ROOT, 'lib/json.jar');
const BUILD = '/tmp/rm_build_public';
const OUT = '/tmp/rm_out_public';
const FIX = path.join(ROOT, 'fixtures');
const GOLD = path.join(__dirname, 'golden');

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

try {
  cp.execFileSync('/usr/local/bin/relicmaze-ensure-db.sh', [], { stdio: 'ignore' });
} catch (e) {
  /* ignore */
}

rmrf(BUILD);
fs.mkdirSync(BUILD, { recursive: true });
cp.execFileSync('javac', ['-cp', LIB, '-d', BUILD].concat(walk(SRC)), { stdio: 'inherit' });
rmrf(OUT);
fs.mkdirSync(OUT, { recursive: true });
cp.execFileSync('java', ['-cp', BUILD + ':' + LIB, 'com.relicmaze.BatchRunner', FIX, OUT], { stdio: 'inherit' });

const names = fs.readdirSync(GOLD).filter((f) => f.endsWith('.txt')).map((f) => f.slice(0, -4)).sort();
let passed = 0;
for (const name of names) {
  const expected = rstrip(fs.readFileSync(path.join(GOLD, name + '.txt'), 'utf8'));
  let actual;
  try {
    actual = rstrip(fs.readFileSync(path.join(OUT, name + '.txt'), 'utf8'));
  } catch (e) {
    actual = '<<no output>>';
  }
  if (actual === expected) {
    passed++;
    console.log('PASS ' + name);
  } else {
    console.log('FAIL ' + name);
    console.log('  expected:\n' + expected.split('\n').map((l) => '    ' + l).join('\n'));
    console.log('  actual:\n' + actual.split('\n').map((l) => '    ' + l).join('\n'));
  }
}
console.log('\n' + passed + '/' + names.length + ' sample scenarios passed');
process.exit(passed === names.length ? 0 : 1);
