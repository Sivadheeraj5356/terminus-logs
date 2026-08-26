package role

import (
	"sort"
	"sync"

	"vivostep.local/sim/util"
)

type WorkItem struct {
	Kind  string
	Epoch uint64
	Done  bool
}

type WorkQueue struct {
	mu        sync.Mutex
	items     []WorkItem
	clock     *util.TickClock
	gateTicks map[string]uint64
}

func NewWorkQueue(clock *util.TickClock) *WorkQueue {
	return &WorkQueue{
		clock:     clock,
		gateTicks: make(map[string]uint64),
	}
}

func (q *WorkQueue) Enqueue(kind string, epoch uint64) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.items = append(q.items, WorkItem{Kind: kind, Epoch: epoch})
}

func (q *WorkQueue) PredecessorDone(epoch uint64) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	for _, it := range q.items {
		if it.Kind == "neighbor_replay" && it.Epoch == epoch {
			return it.Done
		}
	}
	return false
}

func (q *WorkQueue) ReleasePending(epoch uint64) {
	q.mu.Lock()
	defer q.mu.Unlock()
	for i := range q.items {
		if q.items[i].Kind == "endpoint_attach" && q.items[i].Epoch == epoch && !q.items[i].Done {
			q.items[i].Done = true
			q.gateTicks["endpoint_attach"] = q.clock.Now()
		}
	}
}

func (q *WorkQueue) ReleaseAll(epoch uint64) {
	q.mu.Lock()
	defer q.mu.Unlock()
	for i := range q.items {
		if q.items[i].Epoch == epoch && !q.items[i].Done {
			q.items[i].Done = true
			q.gateTicks[q.items[i].Kind] = q.clock.Now()
		}
	}
}

func (q *WorkQueue) MarkDone(kind string, epoch uint64) {
	q.mu.Lock()
	defer q.mu.Unlock()
	for i := range q.items {
		if q.items[i].Kind == kind && q.items[i].Epoch == epoch {
			q.items[i].Done = true
			q.gateTicks[kind] = q.clock.Now()
		}
	}
}

func (q *WorkQueue) GateTick(kind string) uint64 {
	q.mu.Lock()
	defer q.mu.Unlock()
	return q.gateTicks[kind]
}

func (q *WorkQueue) CompletedKinds() []string {
	q.mu.Lock()
	defer q.mu.Unlock()
	out := make([]string, 0)
	for kind, tick := range q.gateTicks {
		if tick > 0 {
			out = append(out, kind)
		}
	}
	sort.Strings(out)
	return out
}

func (q *WorkQueue) ItemDone(kind string, epoch uint64) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	for _, it := range q.items {
		if it.Kind == kind && it.Epoch == epoch {
			return it.Done
		}
	}
	return false
}

func (q *WorkQueue) HasPendingAttach(epoch uint64) bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	for _, it := range q.items {
		if it.Kind == "endpoint_attach" && it.Epoch == epoch && !it.Done {
			return true
		}
	}
	return false
}

func GateReleaseExported(q *WorkQueue, epoch uint64) error {
	return AdvanceLatchExported(q, epoch)
}
