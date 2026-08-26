package cache

import (
	"sync"
)

// Stats tracks cache hits/misses for operator metrics.
type Stats struct {
	mu    sync.Mutex
	Hits  int64
	Misses int64
	Writes int64
}

func (s *Stats) Hit() {
	s.mu.Lock()
	s.Hits++
	s.mu.Unlock()
}

func (s *Stats) Miss() {
	s.mu.Lock()
	s.Misses++
	s.mu.Unlock()
}

func (s *Stats) Write() {
	s.mu.Lock()
	s.Writes++
	s.mu.Unlock()
}

func (s *Stats) Snapshot() (hits, misses, writes int64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.Hits, s.Misses, s.Writes
}
