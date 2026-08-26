package storage

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"sync"
)

// Memory is an in-process mock object store used by checkpoints and journals.
type Memory struct {
	mu   sync.RWMutex
	data map[string][]byte
}

func NewMemory() *Memory {
	return &Memory{data: map[string][]byte{}}
}

func (m *Memory) Put(key string, value []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	cp := append([]byte{}, value...)
	m.data[key] = cp
}

func (m *Memory) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	v, ok := m.data[key]
	if !ok {
		return nil, false
	}
	return append([]byte{}, v...), true
}

func (m *Memory) Delete(key string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.data, key)
}

func (m *Memory) Keys() []string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make([]string, 0, len(m.data))
	for k := range m.data {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func (m *Memory) PutJSON(key string, v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	m.Put(key, b)
	return nil
}

func (m *Memory) GetJSON(key string, dest any) error {
	b, ok := m.Get(key)
	if !ok {
		return fmt.Errorf("storage: missing key %s", key)
	}
	return json.Unmarshal(b, dest)
}

// Disk is a directory-backed mock blob store.
type Disk struct {
	Root string
}

func NewDisk(root string) (*Disk, error) {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return nil, err
	}
	return &Disk{Root: root}, nil
}

func (d *Disk) path(key string) string {
	return filepath.Join(d.Root, filepath.Clean(key))
}

func (d *Disk) Put(key string, value []byte) error {
	p := d.path(key)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	return os.WriteFile(p, value, 0o644)
}

func (d *Disk) Get(key string) ([]byte, error) {
	return os.ReadFile(d.path(key))
}

func (d *Disk) List(prefix string) ([]string, error) {
	root := d.path(prefix)
	var out []string
	_ = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil || info == nil || info.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(d.Root, path)
		if err != nil {
			return nil
		}
		out = append(out, rel)
		return nil
	})
	sort.Strings(out)
	return out, nil
}
