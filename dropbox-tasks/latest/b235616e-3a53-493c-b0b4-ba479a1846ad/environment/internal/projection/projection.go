package projection

import (
	"encoding/json"
	"os"
	"time"

	"baylock/internal/checkpoint"
	"baylock/internal/domain"
	"baylock/internal/journal"
	"baylock/internal/legacy"
	"baylock/internal/pol"
)

type Snapshot struct {
	GeneratedFrom    string `json:"generated_from"`
	EventLineCount   int    `json:"event_line_count"`
	AppliedCount     int    `json:"applied_count"`
	RejectedCount    int    `json:"rejected_count"`
	ProjectionDigest string `json:"projection_digest"`
}

// Rebuild is unfinished: it does not fold journal events or compute digests.
func Rebuild() (*Snapshot, error) {
	lines, lineCount, malformed, err := journal.ReadAllEvents()
	if err != nil {
		return nil, err
	}
	_ = malformed
	engine := pol.NewEngine()
	cp, err := checkpoint.Load()
	if err != nil {
		return nil, err
	}
	if err := legacy.ApplyIfNeeded(&cp.MigratedLegacy, engine); err != nil {
		return nil, err
	}
	_ = engine
	_ = lines

	snap := &Snapshot{
		GeneratedFrom:  domain.GeneratedFrom,
		EventLineCount: lineCount,
	}
	cp.JournalSeq = len(lines)
	cp.RebuildAt = time.Now().UTC().Format(time.RFC3339)
	if err := checkpoint.Save(cp); err != nil {
		return nil, err
	}
	if err := saveProjection(snap); err != nil {
		return nil, err
	}
	return snap, nil
}

func saveProjection(snap *Snapshot) error {
	data, err := json.MarshalIndent(snap, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/projection.json", data, 0o644)
}

func Load() (*Snapshot, error) {
	data, err := os.ReadFile("/app/state/projection.json")
	if err != nil {
		return nil, err
	}
	var snap Snapshot
	if err := json.Unmarshal(data, &snap); err != nil {
		return nil, err
	}
	return &snap, nil
}
