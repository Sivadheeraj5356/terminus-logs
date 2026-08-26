package report

import (
	"encoding/json"
	"os"
	"path/filepath"

	"ra.local/field/internal/domain"
)

func Write(path string, doc *domain.Attestation) error {
	body, err := json.Marshal(doc)
	if err != nil {
		return err
	}
	body = append(body, '\n')
	parent := filepath.Dir(path)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(parent, ".ra-write-*")
	if err != nil {
		return err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if err := tmp.Chmod(0o644); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(body); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(name, path)
}
