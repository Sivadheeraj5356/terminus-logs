package validate

import (
	"fmt"
	"regexp"
	"strings"
	"unicode"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

var idRe = regexp.MustCompile(`^[a-zA-Z][a-zA-Z0-9_-]{0,63}$`)

// Workflow performs structural validation beyond parser normalization.
func Workflow(wf *model.Workflow) error {
	if wf == nil {
		return fmt.Errorf("nil workflow")
	}
	if strings.TrimSpace(wf.Name) == "" {
		return fmt.Errorf("name required")
	}
	if strings.TrimSpace(wf.Version) == "" {
		return fmt.Errorf("version required")
	}
	if len(wf.Nodes) == 0 {
		return fmt.Errorf("at least one node required")
	}
	seen := map[string]struct{}{}
	for _, n := range wf.Nodes {
		if err := Node(n); err != nil {
			return err
		}
		if _, ok := seen[n.ID]; ok {
			return fmt.Errorf("duplicate node %s", n.ID)
		}
		seen[n.ID] = struct{}{}
	}
	for _, e := range wf.Edges {
		if err := Edge(e, seen); err != nil {
			return err
		}
	}
	for _, n := range wf.Nodes {
		for _, d := range n.DependsOn {
			if _, ok := seen[d]; !ok {
				return fmt.Errorf("node %s depends on unknown %s", n.ID, d)
			}
		}
	}
	return nil
}

func Node(n model.Node) error {
	if !idRe.MatchString(n.ID) {
		return fmt.Errorf("invalid node id %q", n.ID)
	}
	if strings.TrimSpace(n.Type) == "" {
		return fmt.Errorf("node %s missing type", n.ID)
	}
	if n.Weight < 0 {
		return fmt.Errorf("node %s negative weight", n.ID)
	}
	if n.TimeoutMs < 0 {
		return fmt.Errorf("node %s negative timeout", n.ID)
	}
	if n.MaxRetries < 0 {
		return fmt.Errorf("node %s negative retries", n.ID)
	}
	for k, v := range n.Params {
		if strings.TrimSpace(k) == "" {
			return fmt.Errorf("node %s empty param key", n.ID)
		}
		if containsControl(v) {
			return fmt.Errorf("node %s param %s has control chars", n.ID, k)
		}
	}
	return nil
}

func Edge(e model.Edge, nodes map[string]struct{}) error {
	if e.From == "" || e.To == "" {
		return fmt.Errorf("edge endpoints required")
	}
	if e.From == e.To {
		return fmt.Errorf("self-loop on %s", e.From)
	}
	if _, ok := nodes[e.From]; !ok {
		return fmt.Errorf("edge from unknown %s", e.From)
	}
	if _, ok := nodes[e.To]; !ok {
		return fmt.Errorf("edge to unknown %s", e.To)
	}
	return nil
}

func containsControl(s string) bool {
	for _, r := range s {
		if unicode.IsControl(r) && r != '\t' {
			return true
		}
	}
	return false
}

// Plan ensures execution plan invariants used by Stage G.
func Plan(plan *model.ExecutionPlan, wf *model.Workflow) error {
	if plan == nil || wf == nil {
		return fmt.Errorf("nil plan or workflow")
	}
	if plan.WorkflowID != wf.ID {
		return fmt.Errorf("workflow id mismatch")
	}
	if len(plan.Order) != len(wf.Nodes) {
		return fmt.Errorf("order cardinality %d != nodes %d", len(plan.Order), len(wf.Nodes))
	}
	seen := map[string]struct{}{}
	for _, id := range plan.Order {
		if _, ok := seen[id]; ok {
			return fmt.Errorf("duplicate in order: %s", id)
		}
		seen[id] = struct{}{}
	}
	for _, n := range wf.Nodes {
		if _, ok := seen[n.ID]; !ok {
			return fmt.Errorf("missing from order: %s", n.ID)
		}
	}
	index := map[string]int{}
	for i, id := range plan.Order {
		index[id] = i
	}
	for _, e := range plan.Edges {
		fi, fok := index[e.From]
		ti, tok := index[e.To]
		if !fok || !tok {
			return fmt.Errorf("edge references missing node")
		}
		if fi >= ti {
			return fmt.Errorf("edge %s->%s violates order", e.From, e.To)
		}
	}
	return nil
}
