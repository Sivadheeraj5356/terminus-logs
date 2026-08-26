package compile

import (
	"fmt"
	"sort"
	"strings"

	"arctl.local/arctl/model"
)

func scan_inputs(items []model.Piece) []string {
	keys := make([]string, 0, len(items))
	seen := map[string]struct{}{}
	for _, row := range items {
		key := row.Tier + "/" + row.Src + ":" + row.Kind
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := make([]string, 0, len(keys))
	for _, key := range keys {
		out = append(out, fmt.Sprintf("seen %s", key))
	}
	return out
}

func ScanSummary(items []model.Piece) string {
	lines := scan_inputs(items)
	return strings.Join(lines, "\n")
}
