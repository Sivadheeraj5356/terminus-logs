package store

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Catalog struct {
	Objects  map[string]ObjectRef `json:"objects"`
	Tags     map[string]string    `json:"tags"`
	Replicas map[string]string    `json:"replicas"`
}

type ObjectRef struct {
	Tier      int    `json:"tier"`
	BytesRef  string `json:"bytes_ref"`
	Immutable bool   `json:"immutable"`
}

func LoadCatalog(root string) (Catalog, error) {
	path := filepath.Join(root, "fixtures", "store", "catalog.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return Catalog{}, err
	}
	var c Catalog
	if err := json.Unmarshal(raw, &c); err != nil {
		return Catalog{}, err
	}
	return c, nil
}

func ManifestBytes(root, tag string) ([]byte, error) {
	cat, err := LoadCatalog(root)
	if err != nil {
		return nil, err
	}
	objKey, ok := cat.Tags[tag]
	if !ok {
		return nil, os.ErrNotExist
	}
	ref := cat.Objects[objKey]
	return os.ReadFile(filepath.Join(root, "fixtures", "store", "blobs", ref.BytesRef+".bin"))
}
