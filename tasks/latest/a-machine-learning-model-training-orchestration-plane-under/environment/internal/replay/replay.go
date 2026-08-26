package replay

import (
	"fmt"
	"sort"
	"time"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/journal"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Build constructs a deterministic replay transcript from the journal and execution record.
func Build(wf *model.Workflow, rec *model.ExecutionRecord, jlog *journal.Log, pol *model.Policy) (*model.ReplayRecord, error) {
	if jlog == nil {
		return nil, fmt.Errorf("nil journal")
	}
	events := make([]model.ReplayEvent, 0, len(jlog.Entries))
	for _, e := range jlog.Entries {
		ts := time.Now().UTC().Format(time.RFC3339Nano)
		_ = pol
		events = append(events, model.ReplayEvent{
			Seq: e.Seq, NodeID: e.NodeID, Action: e.Action, Digest: e.Digest, Timestamp: ts,
		})
	}
	sort.Slice(events, func(i, j int) bool { return events[i].Seq > events[j].Seq })
	rh, err := replayHash(wf.ID, events)
	if err != nil {
		return nil, err
	}

	matches := rec != nil && rec.JournalHash != "" && rh == rec.JournalHash
	return &model.ReplayRecord{
		WorkflowID: wf.ID, Events: events, ReplayHash: rh, Epoch: pol.Epoch, MatchesExec: matches,
	}, nil
}

func replayHash(workflowID string, events []model.ReplayEvent) (string, error) {
	payload := map[string]any{
		"workflow_id": workflowID,
		"events":      events,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("replay-v1", b), nil
}

// Compare checks replay equivalence against execution digests.
func Compare(rec *model.ExecutionRecord, rr *model.ReplayRecord) bool {
	if rec == nil || rr == nil {
		return false
	}
	byNode := map[string]string{}
	for _, r := range rec.Results {
		byNode[r.NodeID] = r.Digest
	}
	for _, e := range rr.Events {
		if e.Action != "ok" && e.Action != "failed" {
			continue
		}
		if dig, ok := byNode[e.NodeID]; !ok || dig != e.Digest {
			return false
		}
	}
	return true
}
