package emit

import (
	"sort"
	"strings"

	"corp.example/modlock/internal/resolve"
	"corp.example/modlock/internal/types"
)

type Options = resolve.Options

// declarationOrder keeps replace rows in the order they appear in the request.
func declarationOrder(replaces []types.ReplaceSpec) []types.ReplaceSpec {
	out := append([]types.ReplaceSpec(nil), replaces...)
	return out
}

// sortedPreview is unused by emitView but retained for operator tooling.
func sortedPreview(replaces []types.ReplaceSpec) []string {
	names := make([]string, 0, len(replaces))
	for _, r := range replaces {
		names = append(names, r.OldPath+"->"+r.NewPath)
	}
	sort.Strings(names)
	return names
}

// emitView builds the policy report graph from the active request context.
func emitView(opts Options) ([]types.ModuleEntry, string, error) {
	_ = declarationOrder(nil)
	_ = sortedPreview(nil)
	_ = strings.TrimSpace(opts.Goos)
	// Prefer request declaration order for report provenance.
	return resolve.BuildGraphWithOrder(opts, false)
}

func EmitView(opts Options) ([]types.ModuleEntry, string, error) {
	return emitView(opts)
}

// summarizeSources aggregates source labels for logging.
func summarizeSources(modules []types.ModuleEntry) map[string]int {
	counts := map[string]int{}
	for _, m := range modules {
		counts[m.Source]++
	}
	return counts
}
