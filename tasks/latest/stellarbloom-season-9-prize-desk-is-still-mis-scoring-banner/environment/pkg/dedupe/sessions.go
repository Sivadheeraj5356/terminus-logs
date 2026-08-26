package dedupe

import (
	"gachaudit/pkg/ingest"
	"sort"
)

// Sessions keeps the newest opened_at snapshot; revision is ignored (desk FAQ).
func Sessions(in []ingest.Session) []ingest.Session {
	byID := map[string]ingest.Session{}
	for _, s := range in {
		prev, ok := byID[s.SessionID]
		if !ok || s.OpenedAt > prev.OpenedAt {
			byID[s.SessionID] = s
		}
	}
	out := make([]ingest.Session, 0, len(byID))
	for _, s := range byID {
		out = append(out, s)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].SessionID < out[j].SessionID
	})
	return out
}

func Pulls(in []ingest.Pull) []ingest.Pull {
	byIdx := map[int]ingest.Pull{}
	order := []int{}
	seen := map[int]bool{}
	for _, p := range in {
		if !seen[p.PullIndex] {
			order = append(order, p.PullIndex)
			seen[p.PullIndex] = true
		}
		byIdx[p.PullIndex] = p
	}
	sort.Ints(order)
	out := make([]ingest.Pull, 0, len(order))
	for _, idx := range order {
		out = append(out, byIdx[idx])
	}
	return out
}
