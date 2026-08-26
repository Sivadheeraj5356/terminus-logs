package meta

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type TargetsDoc struct {
	Signed struct {
		Version int `json:"version"`
	} `json:"signed"`
}

func TargetsVersion(root string, gen int) (int, []byte, error) {
	name := "targets.v1.json"
	if gen >= 2 {
		name = "targets.v2.json"
	}
	path := filepath.Join(root, "fixtures", "meta", name)
	raw, err := os.ReadFile(path)
	if err != nil {
		return 0, nil, err
	}
	var doc TargetsDoc
	_ = json.Unmarshal(raw, &doc)
	ver := doc.Signed.Version
	if ver == 0 {
		ver = gen
	}
	return ver, raw, nil
}

func RootBytes(root string) ([]byte, error) {
	return os.ReadFile(filepath.Join(root, "fixtures", "meta", "root.json"))
}
