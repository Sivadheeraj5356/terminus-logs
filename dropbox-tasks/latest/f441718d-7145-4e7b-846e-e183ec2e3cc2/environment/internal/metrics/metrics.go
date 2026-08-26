package metrics

import (
	"sort"
	"sync"
)

// Counter is a named monotonic counter.
type Counter struct {
	Name  string
	Value int64
}

// Registry collects deterministic counters for operator dashboards (mocked).
type Registry struct {
	mu       sync.Mutex
	counters map[string]int64
}

func NewRegistry() *Registry {
	return &Registry{counters: map[string]int64{}}
}

func (r *Registry) Inc(name string, delta int64) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.counters[name] += delta
}

func (r *Registry) Get(name string) int64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.counters[name]
}

func (r *Registry) Snapshot() []Counter {
	r.mu.Lock()
	defer r.mu.Unlock()
	names := make([]string, 0, len(r.counters))
	for n := range r.counters {
		names = append(names, n)
	}
	sort.Strings(names)
	out := make([]Counter, 0, len(names))
	for _, n := range names {
		out = append(out, Counter{Name: n, Value: r.counters[n]})
	}
	return out
}

// StageNames lists pipeline stage metric prefixes.
func StageNames() []string {
	return []string{
		"parser", "compiler", "scheduler", "executor",
		"checkpoint", "recovery", "replay", "verification", "certificate",
	}
}
