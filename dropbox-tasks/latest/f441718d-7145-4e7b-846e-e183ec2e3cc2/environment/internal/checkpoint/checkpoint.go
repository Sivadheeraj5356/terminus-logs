package checkpoint

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/journal"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Store persists checkpoints under a directory.
type Store struct {
	Dir string
}

func NewStore(dir string) *Store {
	_ = os.MkdirAll(dir, 0o755)
	return &Store{Dir: dir}
}

// Create builds a checkpoint from the current execution record and journal.
func Create(
	wf *model.Workflow,
	rec *model.ExecutionRecord,
	jlog *journal.Log,
	version int,
	parentID string,
	epoch string,
) (*model.Checkpoint, error) {
	completed := []string{}
	pending := []string{}
	failed := []string{}
	digests := map[string]string{}
	for _, r := range rec.Results {
		digests[r.NodeID] = r.Digest
		switch r.Status {
		case "ok":
			completed = append(completed, r.NodeID)
		case "failed":
			failed = append(failed, r.NodeID)
		default:
			pending = append(pending, r.NodeID)
		}
	}
	sort.Strings(completed)
	sort.Strings(pending)
	sort.Strings(failed)

	jh := rec.JournalHash
	if jh == "" && jlog != nil {
		var err error
		jh, err = jlog.Hash()
		if err != nil {
			return nil, err
		}
	}
	id := hash.Truncate(hash.DomainHash("checkpoint-id", []byte(wf.ID+"\n"+strconv.Itoa(version)+"\n"+jh)), 16)
	created, _ := util.OffsetTimestamp(epoch, version*1000)
	meta := map[string]string{
		"plan_digest": rec.PlanDigest,
		"status":      rec.Status,
	}
	cp := &model.Checkpoint{
		ID: id, WorkflowID: wf.ID, Version: version,
		Completed: completed, Pending: pending, Failed: failed,
		NodeDigests: digests, JournalHash: jh, ParentID: parentID,
		CreatedAt: created, Metadata: meta,
	}
	snap, err := snapshotHash(cp)
	if err != nil {
		return nil, err
	}
	cp.SnapshotHash = snap
	return cp, nil
}

func snapshotHash(cp *model.Checkpoint) (string, error) {
	payload := map[string]any{
		"id":           cp.ID,
		"workflow_id":  cp.WorkflowID,
		"version":      cp.Version,
		"completed":    cp.Completed,
		"pending":      cp.Pending,
		"failed":       cp.Failed,
		"node_digests": cp.NodeDigests,
		"journal_hash": cp.JournalHash,
		"parent_id":    cp.ParentID,
		"metadata":     cp.Metadata,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("checkpoint-snap", b), nil
}

func (s *Store) Save(cp *model.Checkpoint) error {
	path := filepath.Join(s.Dir, fmt.Sprintf("%s-v%d.json", cp.WorkflowID, cp.Version))
	return util.WriteJSON(path, cp)
}

func (s *Store) List(workflowID string) ([]*model.Checkpoint, error) {
	entries, err := os.ReadDir(s.Dir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var out []*model.Checkpoint
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		var cp model.Checkpoint
		if err := util.ReadJSON(filepath.Join(s.Dir, e.Name()), &cp); err != nil {
			continue
		}
		if workflowID != "" && cp.WorkflowID != workflowID {
			continue
		}
		cpCopy := cp
		out = append(out, &cpCopy)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Version < out[j].Version })
	return out, nil
}

// Latest returns the preferred checkpoint for recovery.
// Contract: highest version for the workflow.
func (s *Store) Latest(workflowID string) (*model.Checkpoint, error) {
	list, err := s.List(workflowID)
	if err != nil {
		return nil, err
	}
	if len(list) == 0 {
		return nil, fmt.Errorf("no checkpoints for %s", workflowID)
	}
	return list[0], nil
}

// MergeIncremental merges an incremental checkpoint onto a base.
// Contract: union completed; failed/pending recomputed; digests overlay; metadata merge (base←inc).
func MergeIncremental(base, inc *model.Checkpoint) (*model.Checkpoint, error) {
	if base == nil {
		return inc, nil
	}
	if inc == nil {
		return base, nil
	}
	out := *base
	out.Version = inc.Version
	out.ID = inc.ID
	out.ParentID = base.ID
	out.JournalHash = inc.JournalHash
	out.CreatedAt = inc.CreatedAt
	out.Completed = append([]string{}, inc.Completed...)
	out.Pending = append([]string{}, inc.Pending...)
	out.Failed = append([]string{}, inc.Failed...)
	out.NodeDigests = map[string]string{}
	for k, v := range inc.NodeDigests {
		out.NodeDigests[k] = v
	}
	out.Metadata = map[string]string{}
	for k, v := range inc.Metadata {
		out.Metadata[k] = v
	}

	snap, err := snapshotHash(&out)
	if err != nil {
		return nil, err
	}
	out.SnapshotHash = snap
	return &out, nil
}

// VerifyIntegrity checks SnapshotHash matches recomputed digest.
func VerifyIntegrity(cp *model.Checkpoint) bool {
	if cp == nil {
		return false
	}
	snap, err := snapshotHash(cp)
	if err != nil {
		return false
	}
	return snap == cp.SnapshotHash
}
