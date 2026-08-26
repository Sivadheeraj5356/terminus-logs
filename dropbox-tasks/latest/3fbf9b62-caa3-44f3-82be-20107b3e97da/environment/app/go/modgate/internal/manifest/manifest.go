package manifest

import (
	"encoding/json"
	"os"
	"path/filepath"

	"modgate/internal/models"
)

func Load(path string) (models.Manifest, error) {
	var m models.Manifest
	b, err := os.ReadFile(path)
	if err != nil {
		return m, err
	}
	err = json.Unmarshal(b, &m)
	return m, err
}

func BatchRoot(manifestPath string) string {
	return filepath.Dir(filepath.Dir(manifestPath))
}

func Resolve(root, declared string) string {
	if filepath.IsAbs(declared) {
		return declared
	}
	return filepath.Join(root, declared)
}
