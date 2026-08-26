#!/usr/bin/env bash
set -euo pipefail

cd /app
export PATH="/usr/local/go/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"

# Expand decision-slot identity to include platform and policy revision.
cat > slot/slot.go <<'EOF'
package slot

import (
	"encoding/json"
	"fmt"
	"strings"

	"corp.example/modlock/internal/db"
	"corp.example/modlock/internal/types"
)

type Store struct {
	dbPath string
}

func Open(dbPath string) *Store {
	return &Store{dbPath: dbPath}
}

func fuseSlotKey(path, version, goos, goarch, policyRevision string) string {
	parts := []string{
		strings.TrimSpace(path),
		strings.TrimSpace(version),
		strings.ToLower(strings.TrimSpace(goos)),
		strings.ToLower(strings.TrimSpace(goarch)),
		strings.TrimSpace(policyRevision),
	}
	return strings.Join(parts, "|")
}

func validateIdentity(path, version, goos, goarch, policyRevision string) error {
	if path == "" || version == "" {
		return fmt.Errorf("slot identity missing path/version")
	}
	if goos == "" || goarch == "" {
		return fmt.Errorf("slot identity missing platform")
	}
	if policyRevision == "" {
		return fmt.Errorf("slot identity missing policy revision")
	}
	return nil
}

func (s *Store) Lookup(path, version, goos, goarch, policyRevision string) ([]types.ModuleEntry, bool, error) {
	if err := validateIdentity(path, version, goos, goarch, policyRevision); err != nil {
		return nil, false, err
	}
	_ = fuseSlotKey(path, version, goos, goarch, policyRevision)
	q := fmt.Sprintf(
		`SELECT payload_json FROM decision_cache WHERE path = '%s' AND version = '%s' AND goos = '%s' AND goarch = '%s' AND policy_revision = '%s' LIMIT 1;`,
		db.Escape(path), db.Escape(version), db.Escape(goos), db.Escape(goarch), db.Escape(policyRevision),
	)
	payload, err := db.QueryOne(s.dbPath, q)
	if err != nil || payload == "" {
		return nil, false, nil
	}
	var cached []types.ModuleEntry
	if err := json.Unmarshal([]byte(payload), &cached); err != nil {
		return nil, false, err
	}
	return cached, true, nil
}

func (s *Store) Store(path, version, goos, goarch, policyRevision string, modules []types.ModuleEntry) error {
	if err := validateIdentity(path, version, goos, goarch, policyRevision); err != nil {
		return err
	}
	raw, err := json.Marshal(modules)
	if err != nil {
		return err
	}
	ins := fmt.Sprintf(
		`INSERT OR REPLACE INTO decision_cache(path, version, goos, goarch, policy_revision, payload_json)
		 VALUES('%s','%s','%s','%s','%s','%s');`,
		db.Escape(path), db.Escape(version), db.Escape(goos), db.Escape(goarch),
		db.Escape(policyRevision), db.Escape(string(raw)),
	)
	return db.Exec(s.dbPath, ins)
}

func (s *Store) Clear() error {
	return db.Exec(s.dbPath, `DELETE FROM decision_cache;`)
}

func (s *Store) DropLegacyShortKeys() error {
	// Remove ambiguous rows that only carried path+version semantics.
	return db.Exec(s.dbPath, `DELETE FROM decision_cache WHERE goos = '' OR goarch = '' OR policy_revision = '';`)
}
EOF

# Align report emission with contract-ordered resolve state.
cat > emit/emit.go <<'EOF'
package emit

import (
	"fmt"
	"sort"

	"corp.example/modlock/internal/resolve"
	"corp.example/modlock/internal/types"
)

type Options = resolve.Options

func normalizeModules(modules []types.ModuleEntry) []types.ModuleEntry {
	out := append([]types.ModuleEntry(nil), modules...)
	sort.Slice(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	for i := range out {
		if out[i].Replaces == nil {
			out[i].Replaces = []types.ReplaceSpec{}
		}
	}
	return out
}

func graphFingerprint(modules []types.ModuleEntry) string {
	parts := make([]string, 0, len(modules))
	for _, m := range normalizeModules(modules) {
		parts = append(parts, fmt.Sprintf("%s@%s/%s/%s", m.Path, m.Version, m.Source, m.PolicyDecision))
	}
	return stringsJoin(parts, ";")
}

func stringsJoin(parts []string, sep string) string {
	if len(parts) == 0 {
		return ""
	}
	out := parts[0]
	for i := 1; i < len(parts); i++ {
		out += sep + parts[i]
	}
	return out
}

func emitView(opts Options) ([]types.ModuleEntry, string, error) {
	modules, rev, err := resolve.BuildGraphWithOrder(opts, true)
	if err != nil {
		return nil, "", err
	}
	modules = normalizeModules(modules)
	_ = graphFingerprint(modules)
	return modules, rev, nil
}

func EmitView(opts Options) ([]types.ModuleEntry, string, error) {
	return emitView(opts)
}

func AgreeWithResolve(opts Options) error {
	lockMods, _, err := resolve.BuildGraph(opts)
	if err != nil {
		return err
	}
	repMods, _, err := EmitView(opts)
	if err != nil {
		return err
	}
	if graphFingerprint(lockMods) != graphFingerprint(repMods) {
		return fmt.Errorf("emit view diverged from resolve graph")
	}
	return nil
}
EOF

# Mark completeness only after all pin rows land.
cat > seal/seal.go <<'EOF'
package seal

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"corp.example/modlock/internal/db"
)

const DefaultRevision = "rev20260717"

type pinLine struct {
	Path           string `json:"path"`
	Version        string `json:"version"`
	Goos           string `json:"goos"`
	Goarch         string `json:"goarch"`
	PolicyRevision string `json:"policy_revision"`
	Decision       string `json:"decision"`
}

func loadPinLines(mirrorRoot string) ([]pinLine, error) {
	pinsPath := filepath.Join(mirrorRoot, "policy", "pins.jsonl")
	f, err := os.Open(pinsPath)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var lines []pinLine
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var p pinLine
		if err := json.Unmarshal([]byte(line), &p); err != nil {
			return nil, err
		}
		lines = append(lines, p)
	}
	return lines, scanner.Err()
}

func writeIncomplete(dbPath string, epoch int) error {
	meta := fmt.Sprintf(
		`INSERT OR REPLACE INTO index_meta(id, policy_revision, index_complete, write_epoch)
		 VALUES(1, '%s', 0, %d);`,
		db.Escape(DefaultRevision), epoch,
	)
	return db.Exec(dbPath, meta)
}

func writeComplete(dbPath string, epoch int) error {
	meta := fmt.Sprintf(
		`INSERT OR REPLACE INTO index_meta(id, policy_revision, index_complete, write_epoch)
		 VALUES(1, '%s', 1, %d);`,
		db.Escape(DefaultRevision), epoch,
	)
	return db.Exec(dbPath, meta)
}

func insertPin(dbPath string, p pinLine) error {
	ins := fmt.Sprintf(
		`INSERT OR REPLACE INTO pins(path, version, goos, goarch, policy_revision, decision)
		 VALUES('%s','%s','%s','%s','%s','%s');`,
		db.Escape(p.Path), db.Escape(p.Version), db.Escape(p.Goos),
		db.Escape(p.Goarch), db.Escape(p.PolicyRevision), db.Escape(p.Decision),
	)
	return db.Exec(dbPath, ins)
}

func sealEpoch(dbPath, mirrorRoot string, resume bool) error {
	if err := db.InitSchema(dbPath); err != nil {
		return err
	}
	lines, err := loadPinLines(mirrorRoot)
	if err != nil {
		return err
	}
	start := 0
	if !resume {
		_ = db.Exec(dbPath, `DELETE FROM pins; DELETE FROM decision_cache; DELETE FROM index_meta;`)
	} else {
		countStr, _ := db.QueryOne(dbPath, `SELECT COUNT(*) FROM pins;`)
		if countStr != "" {
			fmt.Sscanf(countStr, "%d", &start)
		}
	}
	if err := writeIncomplete(dbPath, len(lines)); err != nil {
		return err
	}
	for i := start; i < len(lines); i++ {
		if err := insertPin(dbPath, lines[i]); err != nil {
			_ = writeIncomplete(dbPath, len(lines))
			return err
		}
	}
	count, err := PinCount(dbPath)
	if err != nil {
		return err
	}
	if count != len(lines) {
		_ = writeIncomplete(dbPath, len(lines))
		return fmt.Errorf("pin count %d != expected %d", count, len(lines))
	}
	return writeComplete(dbPath, len(lines))
}

func Reindex(mirrorRoot, dbPath string, resume bool) error {
	return sealEpoch(dbPath, mirrorRoot, resume)
}

func QueryComplete(dbPath string) (bool, error) {
	val, err := db.QueryOne(dbPath, `SELECT index_complete FROM index_meta WHERE id = 1;`)
	if err != nil || val == "" {
		return false, nil
	}
	return val == "1", nil
}

func PinCount(dbPath string) (int, error) {
	val, err := db.QueryOne(dbPath, `SELECT COUNT(*) FROM pins;`)
	if err != nil || val == "" {
		return 0, err
	}
	var count int
	fmt.Sscanf(val, "%d", &count)
	return count, nil
}
EOF

# Correct legacy P/W/R mapping and harden migration helpers.
cat > remap/remap.go <<'EOF'
package remap

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"corp.example/modlock/internal/digest"
	"corp.example/modlock/internal/lockfile"
	"corp.example/modlock/internal/types"
)

func mapLegacy(code string) string {
	switch strings.ToUpper(strings.TrimSpace(code)) {
	case "P":
		return "policy"
	case "W":
		return "workspace"
	case "R":
		return "replace"
	default:
		return "allow"
	}
}

func mapSource(code, src string) string {
	switch strings.ToUpper(strings.TrimSpace(code)) {
	case "W":
		return "workspace"
	case "R":
		return "replace"
	default:
		if src != "" {
			return src
		}
		return "mirror"
	}
}

func validateMapped(entry types.ModuleEntry) error {
	switch entry.PolicyDecision {
	case "policy", "workspace", "replace", "allow":
	default:
		return fmt.Errorf("unknown policy_decision %q", entry.PolicyDecision)
	}
	switch entry.Source {
	case "mirror", "workspace", "replace":
	default:
		return fmt.Errorf("unknown source %q", entry.Source)
	}
	return nil
}

func convertModule(m types.V1Module) (types.ModuleEntry, error) {
	entry := types.ModuleEntry{
		Path:           m.Path,
		Version:        m.Version,
		Source:         mapSource(m.PolicyCode, m.Source),
		PolicyDecision: mapLegacy(m.PolicyCode),
		Replaces:       []types.ReplaceSpec{},
	}
	if m.ReplaceOld != "" {
		entry.Replaces = append(entry.Replaces, types.ReplaceSpec{
			OldPath: m.ReplaceOld, NewPath: m.ReplaceNew, NewVersion: m.ReplaceVersion,
		})
	}
	if err := validateMapped(entry); err != nil {
		return types.ModuleEntry{}, err
	}
	return entry, nil
}

func MigrateLock(inPath, outPath string) error {
	raw, err := os.ReadFile(inPath)
	if err != nil {
		return err
	}
	var v1 types.V1Lock
	if err := json.Unmarshal(raw, &v1); err != nil {
		return err
	}
	modules := make([]types.ModuleEntry, 0, len(v1.Modules))
	for _, m := range v1.Modules {
		entry, err := convertModule(m)
		if err != nil {
			return err
		}
		modules = append(modules, entry)
	}
	sort.Slice(modules, func(i, j int) bool { return modules[i].Path < modules[j].Path })
	artifact := types.Artifact{
		SchemaVersion:  lockfile.SchemaVersion,
		Goos:           v1.Goos,
		Goarch:         v1.Goarch,
		PolicyRevision: "rev20260717",
		Modules:        modules,
	}
	artifact.ResolutionDigest = digest.Compute(modules)
	out, err := json.MarshalIndent(artifact, "", "  ")
	if err != nil {
		return err
	}
	out = append(out, '\n')
	return os.WriteFile(outPath, out, 0o644)
}

func DigestV1Lock(inPath string) (string, error) {
	tmp := inPath + ".migrated.json"
	if err := MigrateLock(inPath, tmp); err != nil {
		return "", err
	}
	defer os.Remove(tmp)
	raw, err := os.ReadFile(tmp)
	if err != nil {
		return "", err
	}
	var artifact types.Artifact
	if err := json.Unmarshal(raw, &artifact); err != nil {
		return "", err
	}
	return artifact.ResolutionDigest, nil
}
EOF

go build -o /app/bin/modpolicylock ./cmd/modpolicylock

rm -f /app/var/policy-index/policy.db
/app/bin/modpolicylock reindex \
  --mirror /app/var/module-mirror \
  --db /app/var/policy-index/policy.db

/app/scripts/offline-modpolicy.sh \
  --request /app/workspaces/smoke/request.json \
  --goos linux --goarch amd64 \
  --report /output/policy-report.json \
  --lock /output/modpolicy.lock.json

/app/bin/modpolicy-inspect graph-compare \
  --lock /output/modpolicy.lock.json \
  --report /output/policy-report.json

/app/scripts/offline-modpolicy.sh \
  --request /app/workspaces/platform-pin/request.json \
  --goos linux --goarch arm64 \
  --report /output/policy-report-arm64.json \
  --lock /output/modpolicy-arm64.lock.json

echo "oracle solve complete"
