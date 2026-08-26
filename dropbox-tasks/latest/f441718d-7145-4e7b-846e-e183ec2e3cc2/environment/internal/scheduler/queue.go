package scheduler

import (
	"sort"
)

// Queue is a deterministic ready queue for node IDs.
type Queue struct {
	items []string
}

func NewQueue(ids []string) *Queue {
	q := &Queue{items: append([]string{}, ids...)}
	q.sort()
	return q
}

func (q *Queue) sort() {
	sort.Strings(q.items)
}

func (q *Queue) Push(id string) {
	q.items = append(q.items, id)
	q.sort()
}

func (q *Queue) Pop() (string, bool) {
	if len(q.items) == 0 {
		return "", false
	}
	id := q.items[0]
	q.items = q.items[1:]
	return id, true
}

func (q *Queue) Len() int { return len(q.items) }

func (q *Queue) Snapshot() []string {
	return append([]string{}, q.items...)
}
