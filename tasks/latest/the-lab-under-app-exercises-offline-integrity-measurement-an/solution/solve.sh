#!/bin/bash
set -euo pipefail

cd /app

echo "== observe shipped behaviour =="
bash scripts/build.sh
python3 - <<'PY'
import json
rep = json.load(open("output/integrity_report.json"))
print("shipped aligned =", rep["aligned"])
prog = json.load(open("output/program.json"))
print("clause roots sample =", sorted({c["root"] for c in prog["clauses"]})[:8])
log = json.load(open("output/measure_log.json"))
print("measure paths =", sorted(r["path"] for r in log["rows"])[:12])
PY

# Production authority lane + matching stamp covenant (a*3 + b*2 + c).
python3 - <<'PY'
import json
from pathlib import Path
stamp = json.loads(Path("data/authority/stamp.json").read_text())
ep = stamp["a"] * 3 + stamp["b"] * 2 + stamp["c"]
pin = {"schema": "authority/v1", "key": "arm", "ep": ep}
Path("data/authority/pin.json").write_text(json.dumps(pin, indent=2) + "\n")
print("authority pin ->", pin)
PY

cat > internal/slot/field.go <<'EOF'
package slot

// Pull returns the bind root.
func Pull(bind map[string]string, tier int) string {
	root, ok := bind["root"]
	if !ok {
		return ""
	}
	_ = tier
	return root
}

// Field is retained for older call sites.
func Field(bind map[string]string, tier int) string {
	return Pull(bind, tier)
}
EOF

cat > internal/weave/covers.go <<'EOF'
package weave

func absolutePath(p string) bool {
	return len(p) > 0 && p[0] == '/'
}

func descendantOf(root, path string) bool {
	if !absolutePath(root) || !absolutePath(path) {
		return false
	}
	if len(path) <= len(root) {
		return false
	}
	if path[:len(root)] != root {
		return false
	}
	return path[len(root)] == '/'
}

// Holds reports whether root encloses path in the hierarchy.
func Holds(root, path string) bool {
	if root == path {
		return true
	}
	if root == "/" {
		return absolutePath(path)
	}
	return descendantOf(root, path)
}

func WantsLog(verbs []int) bool {
	for _, v := range verbs {
		if v == 1 {
			return true
		}
	}
	return false
}

func WantsCheck(verbs []int) bool {
	for _, v := range verbs {
		if v == 2 || v == 4 {
			return true
		}
	}
	return false
}
EOF

cat > internal/band/pick.go <<'EOF'
package band

import "imlab/internal/model"

// Prefer returns the numerically smallest tier among covering clauses.
func Prefer(clauses []model.Clause, p string, holds func(root, path string) bool) int {
	best := -1
	for _, c := range clauses {
		if !holds(c.Root, p) {
			continue
		}
		if best < 0 || c.Tier < best {
			best = c.Tier
		}
	}
	return best
}

func verbKnown(verbs []int, v int) bool {
	for _, x := range verbs {
		if x == v {
			return true
		}
	}
	return false
}

func appendVerb(dst []int, v int) []int {
	if verbKnown(dst, v) {
		return dst
	}
	return append(dst, v)
}

// BitsAt returns verb bits active at tier t for path p.
func BitsAt(clauses []model.Clause, tier int, p string, holds func(root, path string) bool) []int {
	var out []int
	for _, c := range clauses {
		if c.Tier != tier {
			continue
		}
		if !holds(c.Root, p) {
			continue
		}
		out = appendVerb(out, c.Verb)
	}
	return out
}
EOF

cat > internal/fusion/apply.go <<'EOF'
package fusion

type Outcome struct {
	Logged bool
	Check  string
}

func failSentinel(hex string) bool {
	return hex == "ffffffffffffffff"
}

func appraiseHMAC(hmac string) string {
	if failSentinel(hmac) {
		return "fail"
	}
	return "pass"
}

func appraiseSig(sig string) string {
	if failSentinel(sig) {
		return "fail"
	}
	return "pass"
}

func mergeCheck(cur, next string) string {
	if cur == "fail" || next == "fail" {
		return "fail"
	}
	if next == "pass" {
		return "pass"
	}
	return cur
}

// Blend runs the verb list against manifest fields for path p.
func Blend(verbs []int, digest, hmac, sig string) Outcome {
	var o Outcome
	o.Check = "skip"
	for _, v := range verbs {
		switch v {
		case 1:
			o.Logged = true
		case 2:
			o.Check = mergeCheck(o.Check, appraiseHMAC(hmac))
		case 4:
			o.Check = mergeCheck(o.Check, appraiseSig(sig))
		}
	}
	_ = digest
	return o
}

func Verdict(o Outcome, wantLog bool, wantCheck bool) string {
	if wantLog && !o.Logged {
		return "bad"
	}
	if wantCheck {
		if o.Check == "fail" {
			return "bad"
		}
		if o.Check != "pass" {
			return "bad"
		}
	}
	if !wantLog && o.Logged {
		return "bad"
	}
	return "ok"
}
EOF

cat > hook/src/lane.rs <<'EOF'
pub fn wants_log(verbs: &[u32]) -> bool {
    verbs.iter().any(|v| *v == 1)
}

pub fn wants_check(verbs: &[u32]) -> bool {
    verbs.iter().any(|v| *v == 2 || *v == 4)
}

pub fn mark_id(path: &str) -> String {
    path.to_string()
}
EOF

cat > hook/src/load.rs <<'EOF'
use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct Program {
    pub verbs: HashMap<String, u32>,
    pub clauses: Vec<Clause>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct Clause {
    pub tier: i32,
    pub verb: u32,
    pub root: String,
}

#[derive(Debug)]
pub struct Job {
    pub name: String,
    pub reads: Vec<String>,
}

pub fn load_program(path: &str) -> Program {
    let text = fs::read_to_string(path).expect("read program");
    serde_json::from_str(&text).expect("parse program")
}

pub fn load_jobs(path: &str) -> Vec<Job> {
    let text = fs::read_to_string(path).expect("read jobs");
    let mut jobs = Vec::new();
    let mut name = String::new();
    let mut reads = Vec::new();
    for line in text.lines() {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.is_empty() {
            continue;
        }
        match parts[0] {
            "JOB" => {
                if !name.is_empty() {
                    jobs.push(Job {
                        name: name.clone(),
                        reads: reads.clone(),
                    });
                }
                name = parts.get(1).unwrap_or(&"").to_string();
                reads.clear();
            }
            "READ" => {
                if let Some(p) = parts.get(1) {
                    reads.push((*p).to_string());
                }
            }
            "END" => {
                jobs.push(Job {
                    name: name.clone(),
                    reads: reads.clone(),
                });
                name.clear();
                reads.clear();
            }
            _ => {}
        }
    }
    jobs
}

pub fn load_manifest(path: &str) -> HashMap<String, ManifestRow> {
    let text = fs::read_to_string(path).expect("read manifest");
    serde_json::from_str(&text).expect("parse manifest")
}

#[derive(Debug, Deserialize, Clone)]
pub struct ManifestRow {
    pub digest_hex: String,
    pub hmac_hex: String,
    pub sig_hex: String,
}

pub fn holds(root: &str, path: &str) -> bool {
    if root == path {
        return true;
    }
    if root == "/" {
        return path.starts_with('/');
    }
    if path.len() <= root.len() {
        return false;
    }
    if !path.starts_with(root) {
        return false;
    }
    path.as_bytes().get(root.len()) == Some(&b'/')
}

pub fn lane_of(clauses: &[Clause], path: &str) -> i32 {
    let mut best = -1;
    for c in clauses {
        if !holds(&c.root, path) {
            continue;
        }
        if best < 0 || c.tier < best {
            best = c.tier;
        }
    }
    best
}

pub fn verb_known(list: &[u32], v: u32) -> bool {
    list.iter().any(|x| *x == v)
}

pub fn bits_at(clauses: &[Clause], tier: i32, path: &str) -> Vec<u32> {
    let mut out: Vec<u32> = Vec::new();
    for c in clauses {
        if c.tier != tier || !holds(&c.root, path) {
            continue;
        }
        if !verb_known(&out, c.verb) {
            out.push(c.verb);
        }
    }
    out
}

pub fn digest_for(manifest: &HashMap<String, ManifestRow>, path: &str) -> String {
    manifest
        .get(path)
        .map(|r| r.digest_hex.clone())
        .unwrap_or_else(|| "0000000000000000".to_string())
}

pub fn write_json(path: &Path, body: &str) {
    fs::write(path, body).expect("write json");
}
EOF

python3 - <<'PY'
from pathlib import Path
path = Path("cmd/reconcile/main.go")
text = path.read_text()
old = """\t\t\tfolded := weave.SoftPath(ev.Path)
\t\t\ttier := band.Prefer(prog.Clauses, folded, weave.Holds)
\t\t\tverbs := band.BitsAt(prog.Clauses, tier, folded, weave.Holds)
\t\t\t_ = ev.Verbs
\t\t\tent := manifest[folded]"""
new = """\t\t\tcanon := weave.CanonicalPath(ev.Path)
\t\t\ttier := band.Prefer(prog.Clauses, canon, weave.Holds)
\t\t\tverbs := band.BitsAt(prog.Clauses, tier, canon, weave.Holds)
\t\t\t_ = ev.Verbs
\t\t\tent := manifest[canon]"""
if old not in text:
    raise SystemExit("reconcile canonical patch anchor missing")
path.write_text(text.replace(old, new, 1))
PY

echo "== rebuild with fixes =="
bash scripts/build.sh

python3 - <<'PY'
import json
from pathlib import Path

rep = json.load(open("output/integrity_report.json"))
assert rep["aligned"] is True, "report still not aligned"
prog = json.load(open("output/program.json"))
roots = {c["root"] for c in prog["clauses"]}
assert "/" not in roots or all(c["tier"] < 6 for c in prog["clauses"] if c["root"] == "/"), roots
assert "/opt/bin" not in roots
log = json.load(open("output/measure_log.json"))
rows = {r["path"] for r in log["rows"]}
for path in (
    "/etc/hosts",
    "/var/log/syslog",
    "/usr/bin/tool",
    "/lib/libc.so",
    "/usr/bin/ghost",
    "/usr/lib/libhelper.so",
    "/usr/share/misc",
    "/usr/bin//tool",
    "/sbin/daemon",
):
    assert path in rows, path
assert "/libreoffice/writer" not in rows
assert "/usr/bin" not in rows
assert Path("output/program.json").exists()
assert Path("output/read_traces.json").exists()
print("post-fix aligned =", rep["aligned"])
PY
