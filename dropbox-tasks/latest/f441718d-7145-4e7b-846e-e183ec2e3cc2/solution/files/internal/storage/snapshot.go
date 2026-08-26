package storage

import (
	"encoding/json"
	"fmt"
	"sort"
	"time"
)

// SnapshotMeta describes a persisted mock snapshot.
type SnapshotMeta struct {
	ID        string            `json:"id"`
	CreatedAt string            `json:"created_at"`
	Labels    map[string]string `json:"labels"`
	Keys      []string          `json:"keys"`
}

// ExportSnapshot serializes memory store contents with metadata.
func (m *Memory) ExportSnapshot(id, epoch string, labels map[string]string) ([]byte, error) {
	keys := m.Keys()
	payload := map[string]any{
		"id":     id,
		"epoch":  epoch,
		"labels": labels,
		"keys":   keys,
		"values": map[string]json.RawMessage{},
	}
	values := map[string]json.RawMessage{}
	for _, k := range keys {
		if b, ok := m.Get(k); ok {
			values[k] = json.RawMessage(b)
		}
	}
	payload["values"] = values
	return json.MarshalIndent(payload, "", "  ")
}

// ImportSnapshot loads keys from an export blob.
func (m *Memory) ImportSnapshot(blob []byte) (*SnapshotMeta, error) {
	var raw struct {
		ID     string                     `json:"id"`
		Epoch  string                     `json:"epoch"`
		Labels map[string]string          `json:"labels"`
		Keys   []string                   `json:"keys"`
		Values map[string]json.RawMessage `json:"values"`
	}
	if err := json.Unmarshal(blob, &raw); err != nil {
		return nil, err
	}
	keys := append([]string{}, raw.Keys...)
	sort.Strings(keys)
	for _, k := range keys {
		if v, ok := raw.Values[k]; ok {
			m.Put(k, []byte(v))
		}
	}
	created := raw.Epoch
	if created == "" {
		created = time.Time{}.UTC().Format(time.RFC3339)
	}
	return &SnapshotMeta{ID: raw.ID, CreatedAt: created, Labels: raw.Labels, Keys: keys}, nil
}

func (s *SnapshotMeta) String() string {
	return fmt.Sprintf("snapshot %s keys=%d", s.ID, len(s.Keys))
}
