package registry

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
)

type Module struct {
	ModuleID string `json:"module_id"`
	Status   string `json:"status"`
}

type Registry struct {
	path string
	mu   sync.Mutex
	rows []Module
}

func Open(path string) (*Registry, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return nil, err
	}
	r := &Registry{path: path}
	if err := r.loadOrSeed(); err != nil {
		return nil, err
	}
	return r, nil
}

func (r *Registry) loadOrSeed() error {
	raw, err := os.ReadFile(r.path)
	if err == nil && len(raw) > 0 {
		var rows []Module
		if err := json.Unmarshal(raw, &rows); err != nil {
			return err
		}
		r.rows = rows
		return nil
	}
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	r.rows = []Module{
		{ModuleID: "auth-core", Status: "approved"},
		{ModuleID: "billing-api", Status: "approved"},
		{ModuleID: "ingest-worker", Status: "approved"},
		{ModuleID: "notify-hub", Status: "approved"},
		{ModuleID: "gateway", Status: "approved"},
		{ModuleID: "legacy-bridge", Status: "pending"},
	}
	return r.persist()
}

func (r *Registry) persist() error {
	body, err := json.Marshal(r.rows)
	if err != nil {
		return err
	}
	return os.WriteFile(r.path, body, 0o644)
}

func (r *Registry) Close() error {
	return nil
}

func (r *Registry) Status(moduleID string) (string, bool, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, m := range r.rows {
		if m.ModuleID == moduleID {
			return m.Status, true, nil
		}
	}
	return "", false, nil
}

func (r *Registry) ApprovedCount() (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	n := 0
	for _, m := range r.rows {
		if m.Status == "approved" {
			n++
		}
	}
	return n, nil
}
