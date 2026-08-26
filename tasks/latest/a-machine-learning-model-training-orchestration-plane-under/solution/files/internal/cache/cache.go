package cache

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
)

// Store is a file-backed deterministic cache for node execution results.
type Store struct {
	Dir string
	mu  sync.Mutex
}

func New(dir string) *Store {
	_ = os.MkdirAll(dir, 0o755)
	return &Store{Dir: dir}
}

// Key builds a cache key.
// Contract: DomainHash("cache-v1", workflowID + "\n" + nodeID + "\n" + paramsDigest + "\n" + version)
func Key(workflowID, nodeID, paramsDigest, version string) string {
	payload := []byte(workflowID + "\n" + nodeID + "\n" + paramsDigest + "\n" + version)
	return hash.DomainHash("cache-v1", payload)
}

func (s *Store) path(key string) string {
	return filepath.Join(s.Dir, key+".json")
}

func (s *Store) Get(key string, dest any) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	b, err := os.ReadFile(s.path(key))
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	if err := json.Unmarshal(b, dest); err != nil {
		return false, err
	}
	return true, nil
}

func (s *Store) Put(key string, value any) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	b, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(s.path(key), b, 0o644)
}

func (s *Store) Clear() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	entries, err := os.ReadDir(s.Dir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	for _, e := range entries {
		_ = os.Remove(filepath.Join(s.Dir, e.Name()))
	}
	return nil
}
