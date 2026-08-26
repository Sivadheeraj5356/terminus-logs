package recovery

import (
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
	cp, err := store.Latest(wf.ID)
	if err != nil {
		return nil, nil, err
	}

	completedSet := map[string]struct{}{}
	for _, id := range cp.Completed {
		completedSet[id] = struct{}{}
	}

	resumed := []string{}
	for _, id := range cp.Failed {
		resumed = append(resumed, id)
	}
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
	// Also resume orphan nodes present in workflow but missing from plan (should not happen when compiler is correct)
	planSet := map[string]struct{}{}
	for _, id := range plan.Order {
		planSet[id] = struct{}{}
	}
	for _, n := range wf.Nodes {
		if _, ok := planSet[n.ID]; ok {
			continue
		}
		if _, ok := completedSet[n.ID]; !ok {
			resumed = append(resumed, n.ID)
		}
	}
	sort.Strings(resumed)
	resumed = unique(resumed)

	rolled := []string{}
	for _, n := range wf.Nodes {
		if _, ok := completedSet[n.ID]; ok {
			continue
		}
		for _, f := range cp.Failed {
			if f == n.ID {
				rolled = append(rolled, n.ID)
			}
		}
	}
	sort.Strings(rolled)

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
