package lineage

import (
	"fmt"
	"sort"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Record captures provenance for a single node execution.
type Record struct {
	NodeID     string   `json:"node_id"`
	Parents    []string `json:"parents"`
	Digest     string   `json:"digest"`
	Inputs     []string `json:"inputs"`
	ProducedAt string   `json:"produced_at"`
}

// Graph is the full lineage graph for a workflow run.
type Graph struct {
	WorkflowID string   `json:"workflow_id"`
	Records    []Record `json:"records"`
	RootDigest string   `json:"root_digest"`
}

// Build constructs lineage records from plan edges and execution results.
func Build(wf *model.Workflow, plan *model.ExecutionPlan, rec *model.ExecutionRecord) (*Graph, error) {
	parents := map[string][]string{}
	for _, e := range plan.Edges {
		parents[e.To] = append(parents[e.To], e.From)
	}
	for id := range parents {
		sort.Strings(parents[id])
	}
	digestBy := map[string]string{}
	timeBy := map[string]string{}
	for _, r := range rec.Results {
		digestBy[r.NodeID] = r.Digest
		timeBy[r.NodeID] = r.EndedAt
	}
	records := make([]Record, 0, len(wf.Nodes))
	for _, n := range wf.Nodes {
		p := append([]string{}, parents[n.ID]...)
		if len(p) == 0 {
			p = append([]string{}, n.DependsOn...)
			sort.Strings(p)
		}
		inputs := make([]string, 0, len(p))
		for _, pid := range p {
			inputs = append(inputs, fmt.Sprintf("%s:%s", pid, digestBy[pid]))
		}
		records = append(records, Record{
			NodeID: n.ID, Parents: p, Digest: digestBy[n.ID],
			Inputs: inputs, ProducedAt: timeBy[n.ID],
		})
	}
	sort.Slice(records, func(i, j int) bool { return records[i].NodeID < records[j].NodeID })
	root, err := RootDigest(wf.ID, records)
	if err != nil {
		return nil, err
	}
	return &Graph{WorkflowID: wf.ID, Records: records, RootDigest: root}, nil
}

// RootDigest binds all node digests into a single provenance root.
func RootDigest(workflowID string, records []Record) (string, error) {
	ordered := append([]Record{}, records...)
	sort.Slice(ordered, func(i, j int) bool { return ordered[i].NodeID < ordered[j].NodeID })
	var b strings.Builder
	b.WriteString(workflowID)
	b.WriteByte('\n')
	for _, r := range ordered {
		b.WriteString(r.NodeID)
		b.WriteByte(':')
		b.WriteString(r.Digest)
		b.WriteByte(';')
	}
	return hash.DomainHash("lineage-root", []byte(b.String())), nil
}

// Explain returns a human-readable lineage path from roots to nodeID.
func Explain(g *Graph, nodeID string) []string {
	byID := map[string]Record{}
	for _, r := range g.Records {
		byID[r.ID()] = r
	}
	var walk func(string, []string) []string
	walk = func(id string, path []string) []string {
		path = append(path, id)
		rec, ok := byID[id]
		if !ok || len(rec.Parents) == 0 {
			return path
		}
		// Deterministic: follow lexicographically smallest parent chain.
		p := append([]string{}, rec.Parents...)
		sort.Strings(p)
		return walk(p[0], path)
	}
	out := walk(nodeID, nil)
	// reverse to root→node
	for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
		out[i], out[j] = out[j], out[i]
	}
	return out
}

func (r Record) ID() string { return r.NodeID }

// ValidateParents ensures every parent listed exists in the record set.
func ValidateParents(g *Graph) error {
	seen := map[string]struct{}{}
	for _, r := range g.Records {
		seen[r.NodeID] = struct{}{}
	}
	for _, r := range g.Records {
		for _, p := range r.Parents {
			if _, ok := seen[p]; !ok {
				return fmt.Errorf("missing parent %s for %s", p, r.NodeID)
			}
		}
	}
	payload, err := util.CanonicalJSON(g)
	if err != nil {
		return err
	}
	_ = payload
	return nil
}
