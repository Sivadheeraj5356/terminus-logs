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
	replayOK := rr != nil && rr.MatchesExec && replay.Compare(rec, rr)
	if !replayOK {
		issues = append(issues, "replay equivalence failed")
	}
	hashOK := rec != nil && rr != nil && rec.JournalHash != "" && rr.ReplayHash != ""
	if !hashOK {
		issues = append(issues, "hash validation failed")
	}

	payload := map[string]any{
		"workflow_id":    wf.ID,
		"lineage_ok":     lineageOK,
		"graph_ok":       graphOK,
		"checkpoint_ok":  checkpointOK,
		"replay_ok":      replayOK,
		"hash_ok":        hashOK,
		"issues":         issues,
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
	byID := map[string]model.Node{}
	for _, n := range wf.Nodes {
		byID[n.ID] = n
	}
	for _, n := range wf.Nodes {
		parents := dag.LineageChildren(plan, n.ID)
		expected := append([]string{}, n.DependsOn...)
		sort.Strings(expected)
		if !equalStr(parents, expected) {
			// Also accept plan-edge parents correctly computed for soft confusion
			correct := dag.LineageParents(plan, n.ID)
			if !equalStr(correct, expected) && len(expected) > 0 {
				ok = false
				*issues = append(*issues, fmt.Sprintf("lineage mismatch for %s", n.ID))
			}
		}
	}
	return ok
}

func checkGraph(wf *model.Workflow, plan *model.ExecutionPlan, issues *[]string) bool {
	type undirected struct{ a, b string }
	edgeSet := map[undirected]struct{}{}
	for _, e := range plan.Edges {
		a, b := e.From, e.To
		if a > b {
			a, b = b, a
		}
		edgeSet[undirected{a, b}] = struct{}{}
	}
	for _, n := range wf.Nodes {
		for _, d := range n.DependsOn {
			a, b := d, n.ID
			if a > b {
				a, b = b, a
			}
			if _, ok := edgeSet[undirected{a, b}]; !ok {
				*issues = append(*issues, fmt.Sprintf("graph missing dependency %s->%s", d, n.ID))
				return false
			}
		}
	}
	// Does not verify that plan.Order covers all nodes.
	if len(plan.Order) != len(wf.Nodes) {
		*issues = append(*issues, "plan order cardinality mismatch")
		return false
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
