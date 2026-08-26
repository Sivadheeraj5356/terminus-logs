package verification

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/checkpoint"
	"github.com/terminus/ai-workflow-runtime/internal/dag"
	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/replay"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Verify performs Stage G checks across plan, execution, checkpoint, and replay.
func Verify(
	wf *model.Workflow,
	plan *model.ExecutionPlan,
	rec *model.ExecutionRecord,
	cp *model.Checkpoint,
	rr *model.ReplayRecord,
) (*model.VerificationReport, error) {
	issues := []string{}

	lineageOK := checkLineage(wf, plan, &issues)
	graphOK := checkGraph(wf, plan, &issues)
	checkpointOK := checkpoint.VerifyIntegrity(cp)
	if !checkpointOK {
		issues = append(issues, "checkpoint integrity failed")
	}
	replayOK := rr != nil && replay.Compare(rec, rr)
	if !replayOK {
		issues = append(issues, "replay equivalence failed")
	}
	hashOK := rec != nil && cp != nil && rec.JournalHash != "" && cp.JournalHash == rec.JournalHash
	if !hashOK {
		issues = append(issues, "hash validation failed")
	}

	payload := map[string]any{
		"workflow_id":   wf.ID,
		"lineage_ok":    lineageOK,
		"graph_ok":      graphOK,
		"checkpoint_ok": checkpointOK,
		"replay_ok":     replayOK,
		"hash_ok":       hashOK,
		"issues":        issues,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return nil, err
	}
	vh := hash.DomainHash("verification-v1", b)
	return &model.VerificationReport{
		WorkflowID: wf.ID, LineageOK: lineageOK, GraphOK: graphOK,
		CheckpointOK: checkpointOK, ReplayOK: replayOK, HashOK: hashOK,
		Issues: issues, VerificationHash: vh,
	}, nil
}

func checkLineage(wf *model.Workflow, plan *model.ExecutionPlan, issues *[]string) bool {
	ok := true
	for _, n := range wf.Nodes {
		parents := dag.LineageParents(plan, n.ID)
		expected := append([]string{}, n.DependsOn...)
		sort.Strings(expected)
		// Plan edges are the source of truth when depends_on was materialized.
		if len(expected) == 0 {
			expected = parents
		}
		if !equalStr(parents, expected) {
			ok = false
			*issues = append(*issues, fmt.Sprintf("lineage mismatch for %s", n.ID))
		}
	}
	return ok
}

func checkGraph(wf *model.Workflow, plan *model.ExecutionPlan, issues *[]string) bool {
	type directed struct{ from, to string }
	edgeSet := map[directed]struct{}{}
	for _, e := range plan.Edges {
		edgeSet[directed{e.From, e.To}] = struct{}{}
	}
	for _, n := range wf.Nodes {
		for _, d := range n.DependsOn {
			if _, ok := edgeSet[directed{d, n.ID}]; !ok {
				*issues = append(*issues, fmt.Sprintf("graph missing dependency %s->%s", d, n.ID))
				return false
			}
		}
	}
	if len(plan.Order) != len(wf.Nodes) {
		*issues = append(*issues, "plan order cardinality mismatch")
		return false
	}
	seen := map[string]struct{}{}
	for _, id := range plan.Order {
		seen[id] = struct{}{}
	}
	for _, n := range wf.Nodes {
		if _, ok := seen[n.ID]; !ok {
			*issues = append(*issues, "plan missing node "+n.ID)
			return false
		}
	}
	return true
}

func equalStr(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
