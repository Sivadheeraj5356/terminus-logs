package replay

import (
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// EventDigest binds a single replay event.
func EventDigest(e model.ReplayEvent) string {
	payload := map[string]any{
		"seq": e.Seq, "node_id": e.NodeID, "action": e.Action,
		"digest": e.Digest, "timestamp": e.Timestamp,
	}
	b, _ := util.CanonicalJSON(payload)
	return hash.DomainHash("replay-event", b)
}

// SortEvents returns events sorted by ascending seq.
func SortEvents(events []model.ReplayEvent) []model.ReplayEvent {
	out := append([]model.ReplayEvent{}, events...)
	sort.Slice(out, func(i, j int) bool { return out[i].Seq < out[j].Seq })
	return out
}

// NodeOrder extracts node IDs in replay sequence order.
func NodeOrder(rr *model.ReplayRecord) []string {
	events := SortEvents(rr.Events)
	out := make([]string, 0, len(events))
	for _, e := range events {
		out = append(out, e.NodeID)
	}
	return out
}
