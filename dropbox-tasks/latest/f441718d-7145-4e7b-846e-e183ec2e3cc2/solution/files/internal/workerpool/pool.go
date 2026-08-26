package workerpool

import (
	"sort"
)

// Pool models a deterministic worker allocator (no goroutines / no sleeps).
type Pool struct {
	Workers []string
}

func New(workers []string) *Pool {
	w := append([]string{}, workers...)
	sort.Strings(w)
	return &Pool{Workers: w}
}

// Assign returns worker for sequence index.
func (p *Pool) Assign(seq int) string {
	if len(p.Workers) == 0 {
		return "default"
	}
	if seq < 0 {
		seq = 0
	}
	return p.Workers[seq%len(p.Workers)]
}

// Size returns worker count.
func (p *Pool) Size() int { return len(p.Workers) }

// Contains reports whether id is a configured worker.
func (p *Pool) Contains(id string) bool {
	for _, w := range p.Workers {
		if w == id {
			return true
		}
	}
	return false
}
