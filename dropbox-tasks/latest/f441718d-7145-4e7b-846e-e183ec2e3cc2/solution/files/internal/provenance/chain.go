package provenance

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// ChainLink is one step in an execution provenance chain.
type ChainLink struct {
	Index  int    `json:"index"`
	NodeID string `json:"node_id"`
	Digest string `json:"digest"`
	Prev   string `json:"prev"`
	Link   string `json:"link"`
}

// BuildChain constructs a hash chain over execution results in plan order.
func BuildChain(plan *model.ExecutionPlan, rec *model.ExecutionRecord) ([]ChainLink, error) {
	by := rec.ResultByNode()
	prev := hash.DomainHash("chain-genesis", []byte(plan.WorkflowID+"\n"+plan.Digest))
	out := make([]ChainLink, 0, len(plan.Order))
	for i, id := range plan.Order {
		nr, ok := by[id]
		if !ok {
			return nil, fmt.Errorf("missing result for %s", id)
		}
		payload := fmt.Sprintf("%d\n%s\n%s\n%s", i, id, nr.Digest, prev)
		link := hash.DomainHash("chain-link", []byte(payload))
		out = append(out, ChainLink{Index: i, NodeID: id, Digest: nr.Digest, Prev: prev, Link: link})
		prev = link
	}
	return out, nil
}

// Tip returns the final chain link digest.
func Tip(links []ChainLink) string {
	if len(links) == 0 {
		return ""
	}
	return links[len(links)-1].Link
}

// SortLinks sorts by index ascending.
func SortLinks(links []ChainLink) []ChainLink {
	out := append([]ChainLink{}, links...)
	sort.Slice(out, func(i, j int) bool { return out[i].Index < out[j].Index })
	return out
}
