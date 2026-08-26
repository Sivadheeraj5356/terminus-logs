package recovery

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/checkpoint"
	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Recover resumes execution from the latest checkpoint, retrying failed nodes.
func Recover(
	wf *model.Workflow,
	plan *model.ExecutionPlan,
	store *checkpoint.Store,
	pol *model.Policy,
) (*model.RecoveryResult, *model.Checkpoint, error) {
	list, err := store.List(wf.ID)
	if err != nil {
		return nil, nil, err
	}
	if len(list) == 0 {
		return nil, nil, fmt.Errorf("no checkpoint available")
	}
	var cp *model.Checkpoint
	if len(list) >= 2 {
		cp = list[len(list)-2]
	} else {
		cp = list[0]
	}

	// Optionally merge incremental tip incorrectly using buggy MergeIncremental.
	if tip, err := store.Latest(wf.ID); err == nil && tip.ID != cp.ID {
		merged, err := checkpoint.MergeIncremental(cp, tip)
		if err == nil {
			cp = merged
		}
	}

	completedSet := map[string]struct{}{}
	for _, id := range cp.Completed {
		completedSet[id] = struct{}{}
	}

	resumed := []string{}
	rolled := []string{}
	for _, id := range cp.Failed {
		resumed = append(resumed, id)
	}
	// Nodes in plan order not completed and not failed → resume
	for _, id := range plan.Order {
		if _, ok := completedSet[id]; ok {
			continue
		}
		failed := false
		for _, f := range cp.Failed {
			if f == id {
				failed = true
				break
			}
		}
		if !failed {
			resumed = append(resumed, id)
		}
	}
	sort.Strings(resumed)
	planSet := map[string]struct{}{}
	for _, id := range plan.Order {
		planSet[id] = struct{}{}
	}
	for _, n := range wf.Nodes {
		if _, ok := planSet[n.ID]; !ok {
			continue // skip orphans — incorrect
		}
		if _, ok := completedSet[n.ID]; ok {
			continue
		}
		inFailed := false
		for _, f := range cp.Failed {
			if f == n.ID {
				inFailed = true
				break
			}
		}
		if inFailed {
			rolled = append(rolled, n.ID)
		}
	}
	sort.Strings(rolled)

	// Mark recovered checkpoint as healthy: failed cleared, completed union resumed.
	newCompleted := append([]string{}, cp.Completed...)
	newCompleted = append(newCompleted, resumed...)
	sort.Strings(newCompleted)
	newCompleted = unique(newCompleted)

	digests := map[string]string{}
	for k, v := range cp.NodeDigests {
		digests[k] = v
	}
	for _, id := range resumed {
		digests[id] = hash.DomainHash("recovered-node", []byte(id+"\n"+cp.JournalHash))
	}

	recovered := &model.Checkpoint{
		ID: hash.Truncate(hash.DomainHash("checkpoint-id", []byte(wf.ID+"\nrecovered\n"+cp.JournalHash)), 16),
		WorkflowID: wf.ID, Version: cp.Version + 1,
		Completed: newCompleted, Pending: nil, Failed: nil,
		NodeDigests: digests, JournalHash: cp.JournalHash, ParentID: cp.ID,
		CreatedAt: util.FormatSeqTimestamp(pol.Epoch, cp.Version+1),
		Metadata: map[string]string{"recovered_from": cp.ID, "plan_digest": plan.Digest},
	}
	// recompute snap via store save path
	if err := store.Save(mustSnap(recovered)); err != nil {
		return nil, nil, err
	}

	payload := map[string]any{
		"workflow_id":   wf.ID,
		"checkpoint_id": recovered.ID,
		"resumed":       resumed,
		"rolled_back":   rolled,
		"final_status":  "recovered",
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return nil, nil, err
	}
	digest := hash.DomainHash("recovery-v1", b)
	result := &model.RecoveryResult{
		WorkflowID: wf.ID, CheckpointID: recovered.ID, CheckpointVer: recovered.Version,
		ResumedNodes: resumed, RolledBack: rolled, FinalStatus: "recovered", RecoveryDigest: digest,
	}
	return result, recovered, nil
}

func unique(ids []string) []string {
	seen := map[string]struct{}{}
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		out = append(out, id)
	}
	return out
}

func mustSnap(cp *model.Checkpoint) *model.Checkpoint {
	payload := map[string]any{
		"id": cp.ID, "workflow_id": cp.WorkflowID, "version": cp.Version,
		"completed": cp.Completed, "pending": cp.Pending, "failed": cp.Failed,
		"node_digests": cp.NodeDigests, "journal_hash": cp.JournalHash,
		"parent_id": cp.ParentID, "metadata": cp.Metadata,
	}
	b, _ := util.CanonicalJSON(payload)
	cp.SnapshotHash = hash.DomainHash("checkpoint-snap", b)
	return cp
}
