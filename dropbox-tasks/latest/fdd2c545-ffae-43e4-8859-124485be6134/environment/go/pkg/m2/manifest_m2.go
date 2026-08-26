package m2

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const SchemaVersion = "fleet.unit.v1"

type Entry struct {
	Name   string `json:"name"`
	Kind   string `json:"kind"`
	Sha256 string `json:"sha256"`
}

type Manifest struct {
	SchemaVersion string  `json:"schema_version"`
	Entries       []Entry `json:"entries"`
	BundleDigest  string  `json:"bundle_digest"`
}

func fileSha256(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

func BuildManifest(unitsDir string) (Manifest, error) {
	ents, err := os.ReadDir(unitsDir)
	if err != nil {
		return Manifest{}, err
	}
	var entries []Entry
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		digest, err := fileSha256(filepath.Join(unitsDir, name))
		if err != nil {
			return Manifest{}, err
		}
		kind := "service"
		// BUG: slice units are tagged as service in manifest entries.
		if strings.HasSuffix(name, ".slice") {
			kind = "service"
		}
		entries = append(entries, Entry{Name: name, Kind: kind, Sha256: digest})
	}
	// BUG: bundle_digest uses insertion order, not sorted-by-name entries.
	canon, err := json.Marshal(entries)
	if err != nil {
		return Manifest{}, err
	}
	sum := sha256.Sum256(canon)
	return Manifest{
		SchemaVersion: SchemaVersion,
		Entries:       entries,
		BundleDigest:  hex.EncodeToString(sum[:]),
	}, nil
}

func SortedEntries(entries []Entry) []Entry {
	out := append([]Entry(nil), entries...)
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func CanonicalBundleDigest(entries []Entry) string {
	sorted := SortedEntries(entries)
	canon, _ := json.Marshal(sorted)
	sum := sha256.Sum256(canon)
	return hex.EncodeToString(sum[:])
}
