package parser

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// RawWorkflow is the on-disk workflow definition schema.
type RawWorkflow struct {
	Name     string            `json:"name"`
	Version  string            `json:"version"`
	Metadata map[string]string `json:"metadata"`
	Nodes    []RawNode         `json:"nodes"`
	Edges    []RawEdge         `json:"edges"`
}

type RawNode struct {
	ID         string            `json:"id"`
	Name       string            `json:"name"`
	Type       string            `json:"type"`
	TimeoutMs  int               `json:"timeout_ms"`
	MaxRetries int               `json:"max_retries"`
	DependsOn  []string          `json:"depends_on"`
	Params     map[string]string `json:"params"`
	Weight     int               `json:"weight"`
}

type RawEdge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

// ParseFile loads and normalizes a workflow definition.
func ParseFile(path, epoch string) (*model.Workflow, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(b, epoch)
}

// Parse validates schema and produces a normalized workflow.
func Parse(data []byte, epoch string) (*model.Workflow, error) {
	var raw RawWorkflow
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parse workflow: %w", err)
	}
	if strings.TrimSpace(raw.Name) == "" {
		return nil, fmt.Errorf("workflow name required")
	}
	if strings.TrimSpace(raw.Version) == "" {
		raw.Version = "1"
	}
	if epoch == "" {
		epoch = util.DefaultEpoch
	}

	name := normalizeText(raw.Name)
	version := strings.TrimSpace(raw.Version)
	idPayload := []byte(name + "\n" + version)
	id := hash.Truncate(hash.DomainHash("workflow-id", idPayload), 16)

	meta := normalizeMetadata(raw.Metadata)
	nodes := make([]model.Node, 0, len(raw.Nodes))
	seen := map[string]struct{}{}
	for _, rn := range raw.Nodes {
		nid := strings.TrimSpace(rn.ID)
		if nid == "" {
			return nil, fmt.Errorf("node id required")
		}
		if _, ok := seen[nid]; ok {
			return nil, fmt.Errorf("duplicate node id %q", nid)
		}
		seen[nid] = struct{}{}
		nname := normalizeText(rn.Name)
		if nname == "" {
			nname = nid
		}
		ntype := strings.TrimSpace(rn.Type)
		if ntype == "" {
			ntype = "task"
		}
		deps := make([]string, 0, len(rn.DependsOn))
		for _, d := range rn.DependsOn {
			d = strings.TrimSpace(d)
			if d != "" {
				deps = append(deps, d)
			}
		}
		sort.Strings(deps)
		params := normalizeMetadata(rn.Params)
		weight := rn.Weight
		if weight <= 0 {
			weight = 1
		}
		nodes = append(nodes, model.Node{
			ID: nid, Name: nname, Type: ntype,
			TimeoutMs: rn.TimeoutMs, MaxRetries: rn.MaxRetries,
			DependsOn: deps, Params: params, Weight: weight,
		})
	}
	sort.Slice(nodes, func(i, j int) bool { return nodes[i].ID < nodes[j].ID })

	edges := make([]model.Edge, 0, len(raw.Edges))
	for _, re := range raw.Edges {
		from, to := strings.TrimSpace(re.From), strings.TrimSpace(re.To)
		if from == "" || to == "" {
			continue
		}
		edges = append(edges, model.Edge{From: from, To: to})
	}
	for _, n := range nodes {
		for _, d := range n.DependsOn {
			edges = append(edges, model.Edge{From: d, To: n.ID})
		}
	}
	edges = normalizeEdges(edges)

	wf := &model.Workflow{
		ID: id, Name: name, Version: version, Epoch: epoch,
		Metadata: meta, Nodes: nodes, Edges: edges,
	}
	return wf, nil
}

func normalizeText(s string) string {
	s = norm.NFC.String(s)
	return util.CollapseWS(s)
}

func normalizeMetadata(m map[string]string) map[string]string {
	out := map[string]string{}
	if m == nil {
		return out
	}
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		nk := strings.TrimSpace(strings.ToLower(k))
		if nk == "" {
			continue
		}
		out[nk] = util.CollapseWS(m[k])
	}
	return out
}

func normalizeEdges(edges []model.Edge) []model.Edge {
	type key struct{ f, t string }
	seen := map[key]struct{}{}
	out := make([]model.Edge, 0, len(edges))
	for _, e := range edges {
		k := key{e.From, e.To}
		if _, ok := seen[k]; ok {
			continue
		}
		seen[k] = struct{}{}
		out = append(out, e)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].From != out[j].From {
			return out[i].From < out[j].From
		}
		return out[i].To < out[j].To
	})
	return out
}

// CanonicalDigest returns DomainHash("workflow-canon", canonical JSON of workflow).
func CanonicalDigest(wf *model.Workflow) (string, error) {
	payload := map[string]any{
		"id":       wf.ID,
		"name":     wf.Name,
		"version":  wf.Version,
		"epoch":    wf.Epoch,
		"metadata": wf.Metadata,
		"nodes":    wf.Nodes,
		"edges":    wf.Edges,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("workflow-canon", b), nil
}

func ValidateASCIIID(id string) bool {
	for _, r := range id {
		if r > unicode.MaxASCII || unicode.IsSpace(r) {
			return false
		}
	}
	return id != ""
}
