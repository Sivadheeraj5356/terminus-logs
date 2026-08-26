package state

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

type JournalEntry struct {
	Generation uint64 `json:"generation"`
	Marker     string `json:"marker"`
	Tick       uint64 `json:"tick"`
}

type Journal struct {
	path    string
	entries []JournalEntry
	head    uint64
}

func OpenJournal(root string) (*Journal, error) {
	j := &Journal{path: filepath.Join(root, "journal.json")}
	if err := j.load(); err != nil && !os.IsNotExist(err) {
		return nil, err
	}
	return j, nil
}

func (j *Journal) load() error {
	b, err := os.ReadFile(j.path)
	if err != nil {
		return err
	}
	var payload struct {
		Entries []JournalEntry `json:"entries"`
		Head    uint64         `json:"head"`
	}
	if err := json.Unmarshal(b, &payload); err != nil {
		return err
	}
	j.entries = payload.Entries
	j.head = payload.Head
	return nil
}

func (j *Journal) Persist() error {
	if err := os.MkdirAll(filepath.Dir(j.path), 0o755); err != nil {
		return err
	}
	payload := struct {
		Entries []JournalEntry `json:"entries"`
		Head    uint64         `json:"head"`
	}{
		Entries: j.entries,
		Head:    j.head,
	}
	b, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	return os.WriteFile(j.path, b, 0o644)
}

func (j *Journal) HeadGeneration() uint64 {
	return j.head
}

func (j *Journal) LastEventTick() uint64 {
	if len(j.entries) == 0 {
		return 0
	}
	return j.entries[len(j.entries)-1].Tick
}

func (j *Journal) Append(generation uint64, marker string, tick uint64) {
	j.entries = append(j.entries, JournalEntry{Generation: generation, Marker: marker, Tick: tick})
	if generation > j.head {
		j.head = generation
	}
}

func (j *Journal) TrimBelow(keepFrom uint64) int {
	out := make([]JournalEntry, 0, len(j.entries))
	removed := 0
	for _, e := range j.entries {
		if e.Generation < keepFrom {
			removed++
			continue
		}
		out = append(out, e)
	}
	j.entries = out
	if j.head < keepFrom {
		j.head = keepFrom
	}
	return removed
}

func TrimStaleExported(j *Journal, keepFrom uint64) (int, error) {
	return ReconcileHeadExported(j, keepFrom)
}

func (j *Journal) ExportSnapshot() []JournalEntry {
	cp := make([]JournalEntry, len(j.entries))
	copy(cp, j.entries)
	sort.Slice(cp, func(i, k int) bool { return cp[i].Generation < cp[k].Generation })
	return cp
}
