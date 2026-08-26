package drift

import "dschedsim/internal/graph"

type Queue struct {
	items []*graph.Job
}

func NewQueue() *Queue {
	return &Queue{}
}

func (q *Queue) Enqueue(j *graph.Job) {
	q.items = append(q.items, j)
}

func (q *Queue) Pop() *graph.Job {
	if len(q.items) == 0 {
		return nil
	}
	j := q.items[0]
	q.items = q.items[1:]
	return j
}

func (q *Queue) Depth() int {
	return len(q.items)
}

func (q *Queue) JobIDs() []string {
	out := make([]string, 0, len(q.items))
	for _, j := range q.items {
		out = append(out, j.Spec.JobID)
	}
	return out
}

func (q *Queue) Clear() {
	q.items = nil
}

// Stub: per-tick dispatch width from free node count per build_obligations.md.
func MaxDispatch(freeNodes int) int {
	_ = freeNodes
	return 1
}
