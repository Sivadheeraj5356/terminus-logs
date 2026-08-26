package fixtures

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"sort"
)

// GoldenFile is a named expected artifact hash.
type GoldenFile struct {
	Rel  string
	Hash string
}

// HashFile returns sha256 hex of a file.
func HashFile(path string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:]), nil
}

// CollectHashes hashes all regular files under root with relative paths.
func CollectHashes(root string) ([]GoldenFile, error) {
	var out []GoldenFile
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil || info == nil || info.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return nil
		}
		h, err := HashFile(path)
		if err != nil {
			return nil
		}
		out = append(out, GoldenFile{Rel: rel, Hash: h})
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Rel < out[j].Rel })
	return out, nil
}
