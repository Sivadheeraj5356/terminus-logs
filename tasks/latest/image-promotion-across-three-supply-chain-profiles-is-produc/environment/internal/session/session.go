package session

import (
	"encoding/json"
	"os"
	"path/filepath"

	"kvlab/internal/row"
)

const RelPath = "state/session_kv.json"

type File struct {
	Profiles []string      `json:"profiles"`
	Runs     []row.RunRow  `json:"runs"`
}

func Path(root string) string {
	return filepath.Join(root, "..", RelPath)
}

func Load(root string) (File, error) {
	path := Path(root)
	raw, err := os.ReadFile(path)
	if err != nil {
		return File{}, nil
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return File{}, err
	}
	return f, nil
}

func Save(root string, f File) error {
	path := Path(root)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(f)
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}
