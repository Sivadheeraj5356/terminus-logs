package executor

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/cache"
	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/journal"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/scheduler"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Run executes the scheduled plan deterministically (mocked, no sleeps/network).
func Run(
	wf *model.Workflow,
	plan *model.ExecutionPlan,
	assignments []scheduler.Assignment,
	pol *model.Policy,
	store *cache.Store,
	failNode string,
) (*model.ExecutionRecord, *journal.Log, error) {
	byID := map[string]model.Node{}
	for _, n := range wf.Nodes {
		byID[n.ID] = n
	}
	assignBy := map[string]scheduler.Assignment{}
	for _, a := range assignments {
		assignBy[a.NodeID] = a
	}

	order := append([]string{}, plan.Order...)
	jlog := journal.New(wf.ID)
	results := make([]model.NodeResult, 0, len(order))
	seq := 0
	for _, nodeID := range order {
		n := byID[nodeID]
		a := assignBy[nodeID]
		paramsDigest, err := paramsHash(n.Params)
		if err != nil {
			return nil, nil, err
		}
		ck := cache.Key(wf.ID, nodeID, paramsDigest, wf.Version)
		var cached model.NodeResult
		if ok, _ := store.Get(ck, &cached); ok {
			results = append(results, cached)
			jlog.Append(nodeID, cached.Status, cached.Digest, cached.StartedAt, map[string]string{
				"worker": cached.WorkerID, "cache": "hit",
			})
			seq++
			continue
		}

		attempts := 1
		status := "ok"
		output := mockOutput(wf, n, a, pol)
		if failNode != "" && nodeID == failNode {
			status = "failed"
			attempts = a.MaxRetries
			output = output + "|injected-fail"
		}

		started, _ := util.OffsetTimestamp(pol.Epoch, seq*1000)
		ended, _ := util.OffsetTimestamp(pol.Epoch, seq*1000+500)
		digest := hash.DomainHash("node-result", []byte(nodeID+"\n"+output+"\n"+status))
		nr := model.NodeResult{
			NodeID: nodeID, Status: status, Attempts: attempts,
			Output: output, Digest: digest, StartedAt: started, EndedAt: ended, WorkerID: a.WorkerID,
		}
		results = append(results, nr)
		jlog.Append(nodeID, status, digest, started, map[string]string{"worker": a.WorkerID})
		_ = store.Put(ck, nr)
		seq++
	}

	sort.SliceStable(results, func(i, j int) bool { return results[i].NodeID < results[j].NodeID })

	jh, err := jlog.Hash()
	if err != nil {
		return nil, nil, err
	}
	completed, _ := util.OffsetTimestamp(pol.Epoch, seq*1000)
	status := "completed"
	for _, r := range results {
		if r.Status != "ok" {
			status = "partial"
			break
		}
	}
	rec := &model.ExecutionRecord{
		WorkflowID: wf.ID, PlanDigest: plan.Digest, Results: results,
		JournalHash: jh, CompletedAt: completed, Status: status,
	}
	return rec, jlog, nil
}

func paramsHash(params map[string]string) (string, error) {
	b, err := util.CanonicalJSON(params)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("params", b), nil
}

func mockOutput(wf *model.Workflow, n model.Node, a scheduler.Assignment, pol *model.Policy) string {
	payload := fmt.Sprintf("%s|%s|%s|%s|%d", wf.ID, n.ID, n.Type, a.WorkerID, a.TimeoutMs)
	return hash.Truncate(hash.DomainHash("exec-output", []byte(payload+"\n"+pol.Seed)), 24)
}
