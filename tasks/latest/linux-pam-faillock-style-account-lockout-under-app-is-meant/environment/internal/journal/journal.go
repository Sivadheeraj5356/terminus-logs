package journal

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"baylock/internal/config"
)

type BatchRecord struct {
	Name         string `json:"name"`
	File         string `json:"file"`
	EventCount   int    `json:"event_count"`
	DurableBytes int    `json:"durable_bytes"`
}

type Manifest struct {
	Batches []BatchRecord `json:"batches"`
}

func ManifestPath() string {
	return filepath.Join(config.JournalRoot, "manifest.json")
}

func BatchPath(name string) string {
	return filepath.Join(config.JournalRoot, "batches", name+".jsonl")
}

func LoadManifest() (*Manifest, error) {
	data, err := os.ReadFile(ManifestPath())
	if err != nil {
		if os.IsNotExist(err) {
			return &Manifest{Batches: []BatchRecord{}}, nil
		}
		return nil, err
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

func SaveManifest(m *Manifest) error {
	if err := os.MkdirAll(filepath.Join(config.JournalRoot, "batches"), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(ManifestPath(), data, 0o644)
}

// ImportBatch is unfinished: it does not persist durable batch state yet.
func ImportBatch(name, eventsPath string) (bool, error) {
	_ = name
	_ = eventsPath
	return true, nil
}

func EventCountForBytes(src string) int {
	return len(splitNonBlank(src))
}

func splitNonBlank(src string) []string {
	var out []string
	for _, line := range strings.Split(src, "\n") {
		if strings.TrimSpace(line) != "" {
			out = append(out, line)
		}
	}
	return out
}

// ReadAllEvents is unfinished.
func ReadAllEvents() ([][]byte, int, int, error) {
	return nil, 0, 0, nil
}

// ComputeJournalDigest is unfinished.
func ComputeJournalDigest() (string, error) {
	return "", nil
}
