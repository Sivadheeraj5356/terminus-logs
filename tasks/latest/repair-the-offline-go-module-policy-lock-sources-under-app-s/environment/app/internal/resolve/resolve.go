package resolve

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"corp.example/modlock/slot"
	"corp.example/modlock/internal/db"
	"corp.example/modlock/internal/policy"
	"corp.example/modlock/internal/types"
)

type Options struct {
	RequestPath string
	Goos        string
	Goarch      string
	DBPath      string
	MirrorRoot  string
	Root        string
}

func rankPairs(replaces []types.ReplaceSpec, contractOrder bool) []types.ReplaceSpec {
	out := append([]types.ReplaceSpec(nil), replaces...)
	if contractOrder {
		sort.Slice(out, func(i, j int) bool {
			if out[i].OldPath != out[j].OldPath {
				return out[i].OldPath < out[j].OldPath
			}
			return out[i].NewPath < out[j].NewPath
		})
	}
	return out
}

func pickReplace(path string, replaces []types.ReplaceSpec, contractOrder bool) (string, string, string, []types.ReplaceSpec) {
	var candidates []types.ReplaceSpec
	if contractOrder {
		for _, rep := range rankPairs(replaces, true) {
			if rep.OldPath == path {
				candidates = append(candidates, rep)
			}
		}
	} else {
		for _, rep := range replaces {
			if rep.OldPath == path {
				candidates = append(candidates, rep)
			}
		}
	}
	if len(candidates) == 0 {
		return path, "v1.0.0", "mirror", []types.ReplaceSpec{}
	}
	winner := candidates[len(candidates)-1]
	return winner.NewPath, winner.NewVersion, "replace", []types.ReplaceSpec{winner}
}

func loadRequest(path string) (types.RequestSpec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return types.RequestSpec{}, err
	}
	var req types.RequestSpec
	if err := json.Unmarshal(raw, &req); err != nil {
		return types.RequestSpec{}, err
	}
	return req, nil
}

func workspaceUses(requestPath string) map[string]string {
	uses := map[string]string{}
	workPath := filepath.Join(filepath.Dir(requestPath), "go.work")
	raw, err := os.ReadFile(workPath)
	if err != nil {
		return uses
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "use ") {
			rel := strings.Trim(strings.TrimPrefix(line, "use"), " ()")
			abs := filepath.Join(filepath.Dir(requestPath), rel)
			modPath := filepath.Join(abs, "go.mod")
			modRaw, err := os.ReadFile(modPath)
			if err != nil {
				continue
			}
			for _, ml := range strings.Split(string(modRaw), "\n") {
				ml = strings.TrimSpace(ml)
				if strings.HasPrefix(ml, "module ") {
					modName := strings.Trim(strings.TrimPrefix(ml, "module"), " ")
					uses[modName] = abs
				}
			}
		}
	}
	return uses
}

func buildGraph(opts Options) ([]types.ModuleEntry, string, error) {
	return buildGraphWithOrder(opts, true)
}

func buildGraphWithOrder(opts Options, contractOrder bool) ([]types.ModuleEntry, string, error) {
	req, err := loadRequest(opts.RequestPath)
	if err != nil {
		return nil, "", err
	}
	if err := db.InitSchema(opts.DBPath); err != nil {
		return nil, "", err
	}
	lookup := policy.Open(opts.DBPath)
	complete, _ := lookup.IsComplete()
	if !complete {
		return nil, "", errIndexIncomplete
	}
	policyRevision, err := lookup.Revision()
	if err != nil {
		return nil, "", err
	}

	cacheStore := slot.Open(opts.DBPath)
	if cached, hit, err := cacheStore.Lookup(req.RootModule, req.RootVersion, opts.Goos, opts.Goarch, policyRevision); hit && err == nil {
		return cached, policyRevision, nil
	}

	mirrorRoot := opts.MirrorRoot
	if mirrorRoot == "" {
		mirrorRoot = "/app/var/module-mirror"
	}
	uses := workspaceUses(opts.RequestPath)
	modules := []types.ModuleEntry{}

	rootEntry := resolveModule(req.RootModule, []types.ReplaceSpec{}, uses, lookup, mirrorRoot, opts.Goos, opts.Goarch, policyRevision, contractOrder)
	rootEntry.Replaces = []types.ReplaceSpec{}
	modules = append(modules, rootEntry)

	for _, dep := range mirrorDeps(mirrorRoot, req.RootModule) {
		modules = append(modules, resolveModule(dep, req.Replaces, uses, lookup, mirrorRoot, opts.Goos, opts.Goarch, policyRevision, contractOrder))
	}

	if err := cacheStore.Store(req.RootModule, req.RootVersion, opts.Goos, opts.Goarch, policyRevision, modules); err != nil {
		return modules, policyRevision, err
	}
	return modules, policyRevision, nil
}

func resolveModule(path string, replaces []types.ReplaceSpec, uses map[string]string, lookup *policy.Lookup, mirrorRoot, goos, goarch, policyRevision string, contractOrder bool) types.ModuleEntry {
	// Workspace overlays beat replace directives and org pins for the original path.
	if _, ok := uses[path]; ok {
		version := "v1.0.0"
		if ver, ok := lookup.MirrorDefault(mirrorRoot, path); ok {
			version = ver
		}
		return types.ModuleEntry{
			Path: path, Version: version, Source: "workspace",
			PolicyDecision: "workspace_override", Replaces: []types.ReplaceSpec{},
		}
	}

	cur, version, source, active := pickReplace(path, replaces, contractOrder)
	decision := "allow"
	if source == "replace" {
		decision = "replace_applied"
	}
	if ver, dec, ok, err := lookup.Pin(cur, goos, goarch, policyRevision); ok && err == nil {
		version = ver
		decision = dec
	} else if source == "mirror" {
		if ver, ok := lookup.MirrorDefault(mirrorRoot, cur); ok {
			version = ver
		} else {
			policy.Unauthorized(policy.UnauthorizedToken + ": " + cur)
		}
	} else if source == "replace" {
		if ver, ok := lookup.MirrorDefault(mirrorRoot, cur); ok {
			version = ver
		}
	}
	return types.ModuleEntry{
		Path: cur, Version: version, Source: source,
		PolicyDecision: decision, Replaces: active,
	}
}

func mirrorDeps(mirrorRoot, root string) []string {
	modPath := filepath.Join(mirrorRoot, "cache/download", root, "@v", "v1.0.0.mod")
	raw, err := os.ReadFile(modPath)
	if err != nil {
		return nil
	}
	var deps []string
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "require ") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				deps = append(deps, strings.Trim(fields[1], " "))
			}
		}
	}
	sort.Strings(deps)
	return deps
}

var errIndexIncomplete = &indexIncompleteErr{}

type indexIncompleteErr struct{}

func (e *indexIncompleteErr) Error() string { return "policy index not initialized" }

func BuildGraph(opts Options) ([]types.ModuleEntry, string, error) {
	return buildGraphWithOrder(opts, true)
}

func BuildGraphWithOrder(opts Options, contractOrder bool) ([]types.ModuleEntry, string, error) {
	return buildGraphWithOrder(opts, contractOrder)
}
