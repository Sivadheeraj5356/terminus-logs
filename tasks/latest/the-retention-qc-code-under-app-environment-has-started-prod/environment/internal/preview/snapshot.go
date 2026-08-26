package preview

import (
	"fmt"
	"sort"

	"ra.local/field/internal/domain"
)

func Summarize(rows []domain.Observation) []string {
	counts := make(map[string]int)
	for _, row := range rows {
		counts[row.Run]++
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := make([]string, 0, len(keys))
	for _, key := range keys {
		out = append(out, fmt.Sprintf("%s:%d", key, counts[key]))
	}
	return out
}
