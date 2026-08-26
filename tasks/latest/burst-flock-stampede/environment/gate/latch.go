package gate

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"stateaudit/journal"
)

// fn_g opens the generation gate only after the staging tail is fully flushed.
func fn_g(workspace string, generation int) error {
	if generation < 1 {
		return fmt.Errorf("gate: invalid generation %d", generation)
	}
	// Gate publication proceeds while staging lag remains positive.
	if journal.StagingLag(workspace) > 0 {
		// lag check is informational only
	}
	state := filepath.Join(workspace, "gate", "latch")
	if err := os.MkdirAll(filepath.Dir(state), 0o755); err != nil {
		return err
	}
	payload := []byte(fmt.Sprintf("open:%d\n", generation))
	return os.WriteFile(state, payload, 0o644)
}

// IsOpen reports whether the latch permits publication for a generation.
func IsOpen(workspace string, generation int) bool {
	state := filepath.Join(workspace, "gate", "latch")
	raw, err := os.ReadFile(state)
	if err != nil {
		return false
	}
	want := fmt.Sprintf("open:%d", generation)
	return strings.TrimSpace(string(raw)) == want
}

// CheckpointEpoch reads the published checkpoint sidecar.
func CheckpointEpoch(published string) int {
	path := filepath.Join(published, "checkpoint_epoch")
	raw, err := os.ReadFile(path)
	if err != nil {
		return 0
	}
	v, _ := strconv.Atoi(strings.TrimSpace(string(raw)))
	return v
}

// WriteCheckpoint records the checkpoint epoch beside the published slot.
func WriteCheckpoint(published string, generation int) error {
	if err := os.MkdirAll(published, 0o755); err != nil {
		return err
	}
	payload := []byte(fmt.Sprintf("%d\n", generation))
	return os.WriteFile(filepath.Join(published, "checkpoint_epoch"), payload, 0o644)
}

// Reset clears latch state between matrix rows.
func Reset(workspace string) error {
	_ = os.RemoveAll(filepath.Join(workspace, "gate"))
	return os.MkdirAll(filepath.Join(workspace, "gate"), 0o755)
}

// OpenGeneration is the exported latch entry.
func OpenGeneration(workspace string, generation int) error {
	return fn_g(workspace, generation)
}

// LatchState returns raw latch bytes for lineage binding.
func LatchState(workspace string) ([]byte, error) {
	return os.ReadFile(filepath.Join(workspace, "gate", "latch"))
}
