#!/bin/bash
set -euo pipefail

ROOT="/app/environment"

cat > "$ROOT/fe-core/src/layer_r4.rs" <<'EOF'
pub fn rank(layer: &str) -> i32 {
    match layer {
        "cli" => 4,
        "env" => 3,
        "manifest" => 2,
        "default" => 1,
        _ => -1,
    }
}

pub fn beats(a: &str, b: &str) -> bool {
    rank(a) > rank(b)
}
EOF

python3 - <<'PY'
from pathlib import Path
p = Path("/app/environment/fe-core/src/resolve_p9.rs")
text = p.read_text(encoding="utf-8")
old = """pub fn pick_list(layers: &[(&str, Option<&Vec<String>>)]) -> Vec<String> {
    // BUG: unions every defined layer instead of replacing with the highest layer.
    let mut merged: Vec<String> = Vec::new();
    for (_, val) in layers {
        if let Some(v) = val {
            for item in v.iter() {
                if !merged.contains(item) {
                    merged.push(item.clone());
                }
            }
        }
    }
    merged
}"""
new = """pub fn pick_list(layers: &[(&str, Option<&Vec<String>>)]) -> Vec<String> {
    let mut best: Option<(&str, &Vec<String>)> = None;
    for (layer, val) in layers {
        if let Some(v) = val {
            match best {
                None => best = Some((layer, v)),
                Some((bl, _)) if layer_r4::beats(layer, bl) => best = Some((layer, v)),
                _ => {}
            }
        }
    }
    best.map(|(_, v)| v.clone()).unwrap_or_default()
}"""
if old not in text:
    raise SystemExit("resolve_p9 pick_list block not found")
p.write_text(text.replace(old, new), encoding="utf-8")
PY

cat > "$ROOT/go/pkg/q3/emit_q3.go" <<'EOF'
package q3

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Doc map[string]json.RawMessage

func readDocs(path string) (map[string]Doc, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out map[string]Doc
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func fieldList(d Doc, key string) []string {
	var items []string
	if err := json.Unmarshal(d[key], &items); err != nil {
		return nil
	}
	return items
}

func fieldStr(d Doc, key string) string {
	var s string
	_ = json.Unmarshal(d[key], &s)
	return s
}

func EmitUnits(resolvedPath, outDir string) error {
	docs, err := readDocs(resolvedPath)
	if err != nil {
		return err
	}
	names := make([]string, 0, len(docs))
	for n := range docs {
		names = append(names, n)
	}
	sort.Strings(names)
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	for _, name := range names {
		d := docs[name]
		var b strings.Builder
		b.WriteString("[Unit]\n")
		after := fieldList(d, "after")
		if len(after) > 0 {
			b.WriteString("After=" + strings.Join(after, " ") + "\n")
		}
		req := fieldList(d, "requires")
		if len(req) > 0 {
			b.WriteString("Requires=" + strings.Join(req, " ") + "\n")
		}
		wants := fieldList(d, "wants")
		if len(wants) > 0 {
			b.WriteString("Wants=" + strings.Join(wants, " ") + "\n")
		}
		b.WriteString("\n[Service]\n")
		b.WriteString("Type=simple\n")
		b.WriteString("ExecStart=/bin/true\n")
		if rs := fieldStr(d, "restart"); rs != "" {
			b.WriteString("Restart=" + rs + "\n")
		}
		if rsec := fieldStr(d, "restart_sec"); rsec != "" {
			b.WriteString("RestartSec=" + rsec + "\n")
		}
		if sl := fieldStr(d, "slice"); sl != "" {
			b.WriteString("Slice=" + sl + "\n")
		}
		body := b.String()
		if err := os.WriteFile(filepath.Join(outDir, name), []byte(body), 0o644); err != nil {
			return err
		}
	}
	sliceBody := "[Unit]\nDescription=Fleet work slice\n"
	if err := os.WriteFile(filepath.Join(outDir, "fleet.work.slice"), []byte(sliceBody), 0o644); err != nil {
		return err
	}
	return nil
}

func UnitNames(dir string) ([]string, error) {
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range ents {
		if !e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	return names, nil
}

func ReadUnit(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

func ParseRequires(body string) []string {
	var out []string
	for _, line := range strings.Split(body, "\n") {
		if strings.HasPrefix(line, "Requires=") {
			out = strings.Fields(strings.TrimPrefix(line, "Requires="))
		}
	}
	return out
}

func FormatRequiresField(units map[string]string) map[string][]string {
	m := make(map[string][]string)
	for name, body := range units {
		m[name] = ParseRequires(body)
	}
	return m
}

func DebugEmit() { fmt.Println("emit_q3") }
EOF

python3 - <<'PY'
from pathlib import Path
p = Path("/app/environment/go/pkg/m2/manifest_m2.go")
text = p.read_text(encoding="utf-8")
text = text.replace(
    '\t\tkind := "service"\n\t\t// BUG: slice units are tagged as service in manifest entries.\n\t\tif strings.HasSuffix(name, ".slice") {\n\t\t\tkind = "service"\n\t\t}',
    '\t\tkind := "service"\n\t\tif strings.HasSuffix(name, ".slice") {\n\t\t\tkind = "slice"\n\t\t}',
)
text = text.replace(
    '\t// BUG: bundle_digest uses insertion order, not sorted-by-name entries.\n\tcanon, err := json.Marshal(entries)',
    '\tentries = SortedEntries(entries)\n\trows := make([]map[string]string, len(entries))\n\tfor i, e := range entries {\n\t\trows[i] = map[string]string{"kind": e.Kind, "name": e.Name, "sha256": e.Sha256}\n\t}\n\tcanon, err := json.Marshal(rows)',
)
p.write_text(text, encoding="utf-8")
PY

cat > "$ROOT/go/pkg/m7/replay_m4.go" <<'EOF'
package m7

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const SchemaVersion = "fleet.unit.v1"

type ScenarioFixture struct {
	Scenario     string   `json:"scenario"`
	Trigger      string   `json:"trigger"`
	UnitsTouched []string `json:"units_touched"`
}

type Event struct {
	Action  string `json:"action"`
	Unit    string `json:"unit"`
	TsIndex int    `json:"ts_index"`
}

type ScenarioOut struct {
	Scenario      string   `json:"scenario"`
	Trigger       string   `json:"trigger"`
	UnitsTouched  []string `json:"units_touched"`
	OrderedEvents []Event  `json:"ordered_events"`
}

type Trace struct {
	SchemaVersion string        `json:"schema_version"`
	Scenarios     []ScenarioOut `json:"scenarios"`
	TraceDigest   string        `json:"trace_digest"`
}

func loadRequires(unitsDir string) map[string][]string {
	out := make(map[string][]string)
	ents, _ := os.ReadDir(unitsDir)
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		raw, _ := os.ReadFile(filepath.Join(unitsDir, e.Name()))
		for _, line := range strings.Split(string(raw), "\n") {
			if strings.HasPrefix(line, "Requires=") {
				out[e.Name()] = strings.Fields(strings.TrimPrefix(line, "Requires="))
			}
		}
	}
	return out
}

func closure(trigger string, requires map[string][]string) map[string]struct{} {
	seen := map[string]struct{}{trigger: {}}
	changed := true
	for changed {
		changed = false
		for unit, deps := range requires {
			for _, dep := range deps {
				if _, ok := seen[dep]; ok {
					if _, have := seen[unit]; !have {
						seen[unit] = struct{}{}
						changed = true
					}
				}
			}
		}
	}
	return seen
}

func dependentsFirst(stopSet map[string]struct{}, requires map[string][]string) []string {
	indeg := map[string]int{}
	adj := map[string][]string{}
	for unit := range stopSet {
		indeg[unit] = 0
	}
	for unit := range stopSet {
		for _, dep := range requires[unit] {
			if _, ok := stopSet[dep]; !ok {
				continue
			}
			adj[unit] = append(adj[unit], dep)
			indeg[dep]++
		}
	}
	var queue []string
	for unit, deg := range indeg {
		if deg == 0 {
			queue = append(queue, unit)
		}
	}
	sort.Strings(queue)
	var order []string
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		order = append(order, node)
		for _, nxt := range adj[node] {
			indeg[nxt]--
			if indeg[nxt] == 0 {
				queue = append(queue, nxt)
				sort.Strings(queue)
			}
		}
	}
	return order
}

func canonicalJSON(v any) ([]byte, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var generic any
	if err := json.Unmarshal(raw, &generic); err != nil {
		return nil, err
	}
	return json.Marshal(generic)
}

func Simulate(unitsDir, scenariosDir string, seed int) (Trace, error) {
	_ = seed
	requires := loadRequires(unitsDir)
	fixtures, _ := filepath.Glob(filepath.Join(scenariosDir, "*.json"))
	sort.Strings(fixtures)
	var scenarios []ScenarioOut
	ts := 0
	for _, fx := range fixtures {
		raw, _ := os.ReadFile(fx)
		var fix ScenarioFixture
		_ = json.Unmarshal(raw, &fix)
		stopSet := closure(fix.Trigger, requires)
		delete(stopSet, fix.Trigger)
		stops := dependentsFirst(stopSet, requires)
		var events []Event
		for _, u := range stops {
			ts++
			events = append(events, Event{Action: "stop", Unit: u, TsIndex: ts})
		}
		ts++
		events = append(events, Event{Action: "stop", Unit: fix.Trigger, TsIndex: ts})
		ts++
		events = append(events, Event{Action: "start", Unit: fix.Trigger, TsIndex: ts})
		scenarios = append(scenarios, ScenarioOut{
			Scenario:      fix.Scenario,
			Trigger:       fix.Trigger,
			UnitsTouched:  fix.UnitsTouched,
			OrderedEvents: events,
		})
	}
	canon, err := canonicalJSON(scenarios)
	if err != nil {
		return Trace{}, err
	}
	sum := sha256.Sum256(canon)
	return Trace{SchemaVersion: SchemaVersion, Scenarios: scenarios, TraceDigest: hex.EncodeToString(sum[:])}, nil
}
EOF

cat > "$ROOT/scripts/pack_tar.py" <<'EOF'
#!/usr/bin/env python3
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path


def entries_digest(entries: list[dict[str, str]]) -> str:
    canon = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).hexdigest()


def main() -> None:
    stage = Path(sys.argv[1])
    out = Path(sys.argv[2])
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    entries = sorted(manifest["entries"], key=lambda e: e["name"])
    manifest["entries"] = entries
    manifest["bundle_digest"] = entries_digest(
        [{"name": e["name"], "kind": e["kind"], "sha256": e["sha256"]} for e in entries]
    )
    with tarfile.open(out, "w") as tar:
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        for ent in entries:
            name = ent["name"]
            path = stage / "units" / name
            tar.add(path, arcname=f"units/{name}")


if __name__ == "__main__":
    main()
EOF

bash "$ROOT/scripts/build.sh"
TB_FLEET_SEED=23 bash "$ROOT/scripts/fleet_pipeline.sh"
