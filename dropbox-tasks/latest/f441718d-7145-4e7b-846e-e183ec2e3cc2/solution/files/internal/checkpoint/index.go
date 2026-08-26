package checkpoint

import (
	"fmt"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// Index is an in-memory view of checkpoints for a workflow.
type Index struct {
	ByVersion map[int]*model.Checkpoint
	ByID      map[string]*model.Checkpoint
}

func BuildIndex(list []*model.Checkpoint) *Index {
	idx := &Index{ByVersion: map[int]*model.Checkpoint{}, ByID: map[string]*model.Checkpoint{}}
	for _, cp := range list {
		idx.ByVersion[cp.Version] = cp
		idx.ByID[cp.ID] = cp
	}
	return idx
}

func (idx *Index) Versions() []int {
	out := make([]int, 0, len(idx.ByVersion))
	for v := range idx.ByVersion {
		out = append(out, v)
	}
	sort.Ints(out)
	return out
}

func (idx *Index) Get(version int) (*model.Checkpoint, error) {
	cp, ok := idx.ByVersion[version]
	if !ok {
		return nil, fmt.Errorf("checkpoint version %d not found", version)
	}
	return cp, nil
}

// DiffCompleted returns nodes completed in b but not a.
func DiffCompleted(a, b *model.Checkpoint) []string {
	aset := a.CompletedSet()
	var out []string
	for _, id := range b.Completed {
		if _, ok := aset[id]; !ok {
			out = append(out, id)
		}
	}
	sort.Strings(out)
	return out
}

// Coverage reports fraction of workflow nodes completed.
func Coverage(cp *model.Checkpoint, totalNodes int) float64 {
	if totalNodes <= 0 {
		return 0
	}
	return float64(len(cp.Completed)) / float64(totalNodes)
}
