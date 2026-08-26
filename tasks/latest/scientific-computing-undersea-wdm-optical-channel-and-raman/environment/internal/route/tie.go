package route

import (
	"strings"

	"splicekit/pkg/model"
)

func pathKey(p []model.Span) string {
	parts := make([]string, len(p))
	for i, s := range p {
		parts[i] = s.ID
	}
	return strings.Join(parts, ">")
}

// Pick selects among equal-length shortest-path candidates.
func Pick(cands [][]model.Span) []model.Span {
	return pick_w(cands)
}

func pick_w(cands [][]model.Span) []model.Span {
	if len(cands) == 0 {
		return nil
	}
	bestIdx := 0
	bestKey := pathKey(cands[0])
	for i := 1; i < len(cands); i++ {
		key := pathKey(cands[i])
		if key > bestKey {
			bestIdx = i
			bestKey = key
		}
	}
	out := make([]model.Span, len(cands[bestIdx]))
	copy(out, cands[bestIdx])
	return out
}
