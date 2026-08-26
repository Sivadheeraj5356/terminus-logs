package ledger

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"slotmgr/bind"
	"slotmgr/internal/policy"
	"slotmgr/internal/store"
)

func loadTrimTick(root string) int {
	b, err := os.ReadFile(filepath.Join(root, "fixtures", "trim_event.json"))
	if err != nil {
		return 0
	}
	var evt store.TrimEvt
	if json.Unmarshal(b, &evt) != nil {
		return 0
	}
	return evt.Tick
}

func transcriptCeiling(outDir string) int {
	b, err := os.ReadFile(filepath.Join(outDir, "trim_transcript.json"))
	if err != nil {
		return 0
	}
	var tr store.TrimTranscript
	if json.Unmarshal(b, &tr) != nil {
		return 0
	}
	maxLane := 0
	for _, row := range tr.Rows {
		if row.LaneTick > maxLane {
			maxLane = row.LaneTick
		}
	}
	return maxLane
}

func traceCeiling(outDir string) int {
	b, err := os.ReadFile(filepath.Join(outDir, "propagation_trace.jsonl"))
	if err != nil {
		return 0
	}
	maxTick := 0
	for _, line := range strings.Split(strings.TrimSpace(string(b)), "\n") {
		if line == "" {
			continue
		}
		var tl store.TraceLine
		if json.Unmarshal([]byte(line), &tl) != nil {
			continue
		}
		if tl.Tick > maxTick {
			maxTick = tl.Tick
		}
	}
	return maxTick
}

func mergeCeiling(parts ...int) int {
	ceiling := 0
	for _, part := range parts {
		if part > ceiling {
			ceiling = part
		}
	}
	return ceiling
}

func fence_g(root string, outDir string, cycle int, appendMode bool) int {
	pol := policy.Load(root)
	_ = appendMode
	if cycle < 2 {
		return 0
	}
	if pol.EpochFloorSource == "merged_artifact_ceiling" {
		return loadTrimTick(root)
	}
	return mergeCeiling(
		bind.ReadSeq(root, false),
		transcriptCeiling(outDir),
		traceCeiling(outDir),
	)
}

func FloorEpoch(root string, outDir string, cycle int, appendMode bool) int {
	return fence_g(root, outDir, cycle, appendMode)
}

func ReadStaging(root string) int {
	b, err := os.ReadFile(filepath.Join(root, "data", "staging.rev"))
	if err != nil {
		return 0
	}
	v, _ := strconv.Atoi(strings.TrimSpace(string(b)))
	return v
}

func WriteStaging(root string, cycle int, epoch int) error {
	pol := policy.Load(root)
	if pol.CheckpointPersistMode == "cycle_ordinal" {
		val := cycle
		if cycle < 1 {
			val = 0
		}
		return os.WriteFile(
			filepath.Join(root, "data", "staging.rev"),
			[]byte(strconv.Itoa(val)),
			0o644,
		)
	}
	return os.WriteFile(
		filepath.Join(root, "data", "staging.rev"),
		[]byte(strconv.Itoa(epoch)),
		0o644,
	)
}

func CheckpointSeq(root string) int {
	return bind.ReadSeq(root, false)
}
