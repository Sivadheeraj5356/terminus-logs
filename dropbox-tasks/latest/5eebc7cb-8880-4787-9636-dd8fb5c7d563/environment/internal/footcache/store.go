package footcache

import (
	"sync"

	"fxdesk/internal/model"
)

type Store struct {
	mu      sync.Mutex
	footers map[string][]byte
}

func NewStore() *Store {
	return &Store{footers: make(map[string][]byte)}
}

func (s *Store) GetFooter(path string) ([]byte, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	raw, ok := s.footers[path]
	return raw, ok
}

func (s *Store) PutFooter(path string, raw []byte) {
	s.mu.Lock()
	defer s.mu.Unlock()
	cp := append([]byte(nil), raw...)
	s.footers[path] = cp
}

func (s *Store) ClearFooter(path string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.footers, path)
}

type FlushMode int

const (
	FlushSoft FlushMode = iota
	FlushHard
)

func ApplyWorkState(st *model.WorkState) *Store {
	s := NewStore()
	if st != nil && st.FooterCache != nil {
		for k, v := range st.FooterCache {
			s.footers[k] = append([]byte(nil), v...)
		}
	}
	return s
}

func SnapshotStore(s *Store, st *model.WorkState) {
	if st.FooterCache == nil {
		st.FooterCache = make(map[string][]byte)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	for k, v := range s.footers {
		st.FooterCache[k] = append([]byte(nil), v...)
	}
}
