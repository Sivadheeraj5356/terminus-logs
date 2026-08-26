package manifest

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"zonepub/internal/keys"
)

// ImportLegacySnapshot ingests a v1 operator snapshot into the workspace.
func ImportLegacySnapshot(workspace, snapshotPath string) error {
	data, err := os.ReadFile(snapshotPath)
	if err != nil {
		return err
	}
	var snap SnapshotV1
	if err := json.Unmarshal(data, &snap); err != nil {
		return err
	}
	if snap.SchemaVersion != 1 {
		return fmt.Errorf("unsupported snapshot schema %d", snap.SchemaVersion)
	}
	imported := struct {
		ImportedAt string          `json:"imported_at"`
		Snapshot   SnapshotV1      `json:"snapshot"`
		Keys       []keys.Entry    `json:"keys"`
	}{Snapshot: snap}
	for _, sk := range snap.Keys {
		imported.Keys = append(imported.Keys, keys.Entry{
			ID:        fmt.Sprintf("snap-%d", sk.KeyTag),
			Role:      keys.Role(sk.Role),
			Status:    keys.Status(sk.Status),
			Algorithm: sk.Algorithm,
			Flags:     sk.Flags,
			PublicKey: sk.PublicKey,
			KeyTag:    sk.KeyTag,
		})
	}
	out, err := json.MarshalIndent(imported, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(workspace, "imported-snapshot.json"), out, 0o644)
}

func ReadDocument(path string) (*Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	return &doc, nil
}

func ReadCommitRecord(path string) (*CommitRecord, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cr CommitRecord
	if err := json.Unmarshal(data, &cr); err != nil {
		return nil, err
	}
	return &cr, nil
}

func WriteDocument(path string, doc *Document) error {
	b, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}
