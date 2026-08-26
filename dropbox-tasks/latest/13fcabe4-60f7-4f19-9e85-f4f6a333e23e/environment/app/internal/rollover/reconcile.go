package rollover

import (
	"encoding/json"
	"os"

	"zonepub/internal/keys"
	"zonepub/internal/manifest"
)

type Inputs struct {
	Inventory *keys.Inventory
	Journal   []manifest.JournalKeyState
	Previous  *manifest.Document
	Snapshot  *manifest.SnapshotV1
}

// Reconcile combines inventory, journal, previous manifest, and optional snapshot.
func Reconcile(in Inputs) *Model {
	m := NewModel()
	for _, e := range in.Inventory.Keys {
		key, err := keys.ParseDNSKEY(e)
		if err != nil {
			continue
		}
		lid := keys.DurableID(key)
		m.Set(State{
			LineageID: lid,
			Role:      e.Role,
			Status:    e.Status,
			KeyTag:    e.KeyTag,
			Source:    "inventory",
		})
	}
	for _, js := range in.Journal {
		m.Set(State{
			LineageID: js.LineageID,
			Role:      keys.Role(js.Role),
			Status:    keys.Status(js.Status),
			KeyTag:    js.KeyTag,
			Source:    "journal",
		})
	}
	if in.Previous != nil {
		for _, km := range in.Previous.Keys {
			m.Set(State{
				LineageID: km.LineageID,
				Role:      keys.Role(km.Role),
				Status:    keys.Status(km.Status),
				KeyTag:    km.KeyTag,
				Source:    "previous",
			})
		}
	}
	if in.Snapshot != nil {
		for _, sk := range in.Snapshot.Keys {
			key, err := keys.ParseDNSKEY(keys.Entry{
				Flags: sk.Flags, Algorithm: sk.Algorithm, PublicKey: sk.PublicKey,
			})
			if err != nil {
				continue
			}
			lid := keys.DurableID(key)
			// snapshot overwrites trusted journal transitions
			m.Set(State{
				LineageID: lid,
				Role:      keys.Role(sk.Role),
				Status:    keys.Status(sk.Status),
				KeyTag:    sk.KeyTag,
				Source:    "snapshot",
			})
		}
	}
	return m
}

func LoadSnapshot(path string) (*manifest.SnapshotV1, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var snap manifest.SnapshotV1
	if err := json.Unmarshal(data, &snap); err != nil {
		return nil, err
	}
	return &snap, nil
}
