package vault

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"jwksbound.local/mux/model"
	"jwksbound.local/mux/realms"
	"jwksbound.local/mux/notary"
)

// SeedRows parses the shipped drop-in tree for a profile into overlay rows.
// Scopes are applied so that stronger scopes win over weaker ones, files are
// walked in alphabetical order within a scope, and each raw line keeps its
// row operator (set/append/remove/delete).
func SeedRows(profile string) []model.Row {
	spec := realms.Lookup(profile)
	layout := notary.ReadProfileLayout()[profile]
	runID := ""
	if len(spec.Runs) > 0 {
		runID = spec.Runs[0]
	}
	root := spec.FixtureDir
	scopeOrder := []string{"issuer", "tenant", "cache"}
	var rows []model.Row
	seq := 0
	for _, scope := range scopeOrder {
		dir := filepath.Join(root, scope)
		files, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		names := []string{}
		for _, f := range files {
			if f.IsDir() {
				continue
			}
			names = append(names, f.Name())
		}
		sort.Strings(names)
		for _, name := range names {
			data, err := os.ReadFile(filepath.Join(dir, name))
			if err != nil {
				continue
			}
			for _, raw := range strings.Split(string(data), "\n") {
				line := strings.TrimSpace(raw)
				if line == "" || strings.HasPrefix(line, "#") {
					continue
				}
				seq++
				rows = append(rows, parseLine(line, scope, name, seq, layout, runID))
			}
		}
	}
	return rows
}

func parseLine(line, scope, origin string, seq int, layout model.ProfileLayout, runID string) model.Row {
	row := model.Row{
		Seq:        seq,
		Epoch:      layout.SeedEpoch,
		Generation: layout.SeedGeneration,
		Mark:       layout.SeedMark,
		Phase:      "apply",
		RunID:      runID,
		Scope:      scope,
		Origin:     origin,
	}
	if strings.HasSuffix(line, "!") {
		row.Op = "delete"
		row.Key = strings.TrimSpace(strings.TrimSuffix(line, "!"))
		return row
	}
	if idx := strings.Index(line, "+="); idx >= 0 {
		row.Op = "append"
		row.Key = strings.TrimSpace(line[:idx])
		row.Value = strings.TrimSpace(line[idx+2:])
		return row
	}
	if idx := strings.Index(line, "-="); idx >= 0 {
		row.Op = "remove"
		row.Key = strings.TrimSpace(line[:idx])
		row.Value = strings.TrimSpace(line[idx+2:])
		return row
	}
	idx := strings.Index(line, "=")
	row.Op = "set"
	row.Key = strings.TrimSpace(line[:idx])
	row.Value = strings.TrimSpace(line[idx+1:])
	return row
}
