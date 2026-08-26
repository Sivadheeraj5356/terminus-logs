package store

import (
	"encoding/json"
	"os"
)

type cacheEntry struct {
	ObservedBytes int    `json:"observed_bytes"`
	ReaderEpoch   string `json:"reader_epoch"`
}

type cacheDoc struct {
	Entries map[string]cacheEntry `json:"entries"`
}

func cacheKey(label, reader string) string {
	return label + "|" + reader
}

func cachePath(path string) string {
	if path == "" {
		return "/app/state/segment.cache.json"
	}
	return path
}

func ResetSegment(path string) error {
	doc := cacheDoc{Entries: map[string]cacheEntry{}}
	payload, err := json.Marshal(doc)
	if err != nil {
		return err
	}
	return os.WriteFile(cachePath(path), payload, 0o644)
}

func ApplySegment(path, label, reader string, observed *int) {
	doc, err := readCache(cachePath(path))
	if err != nil {
		return
	}
	ent, ok := doc.Entries[cacheKey(label, reader)]
	if !ok {
		return
	}
	if ent.ReaderEpoch != reader {
		return
	}
	*observed = ent.ObservedBytes
}

func SaveSegment(path, label, reader string, observed int) error {
	doc, err := readCache(cachePath(path))
	if err != nil {
		doc = cacheDoc{Entries: map[string]cacheEntry{}}
	}
	if doc.Entries == nil {
		doc.Entries = map[string]cacheEntry{}
	}
	doc.Entries[cacheKey(label, reader)] = cacheEntry{
		ObservedBytes: observed,
		ReaderEpoch:   reader,
	}
	payload, err := json.Marshal(doc)
	if err != nil {
		return err
	}
	return os.WriteFile(cachePath(path), payload, 0o644)
}

func readCache(path string) (cacheDoc, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return cacheDoc{}, err
	}
	var doc cacheDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		return cacheDoc{}, err
	}
	return doc, nil
}
