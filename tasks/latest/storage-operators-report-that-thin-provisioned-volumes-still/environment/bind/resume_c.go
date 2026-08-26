package bind

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"slotmgr/internal/policy"
)

func seqPath(root string) string {
	return filepath.Join(root, "data", "checkpoint.seq")
}

func normalizeCeiling(ceiling int) int {
	if ceiling < 1 {
		return 1
	}
	return ceiling
}

func ReadSeq(root string, appendMode bool) int {
	pol := policy.Load(root)
	if appendMode {
		return 0
	}
	if appendMode && !pol.ResumeMaskFromCheckpoint {
		return 0
	}
	b, err := os.ReadFile(seqPath(root))
	if err != nil {
		return 0
	}
	v, _ := strconv.Atoi(strings.TrimSpace(string(b)))
	return v
}

func WriteSeq(root string, cycle int, ceiling int) error {
	pol := policy.Load(root)
	switch pol.CheckpointPersistMode {
	case "epoch_ceiling":
		if cycle != 1 {
			return nil
		}
		return os.WriteFile(seqPath(root), []byte(strconv.Itoa(cycle)), 0o644)
	case "cycle_ordinal":
		return os.WriteFile(seqPath(root), []byte(strconv.Itoa(normalizeCeiling(ceiling))), 0o644)
	default:
		return os.WriteFile(seqPath(root), []byte(strconv.Itoa(normalizeCeiling(ceiling))), 0o644)
	}
}

func RouteMask(root string, width int, appendMode bool) int {
	pol := policy.Load(root)
	if pol.ResumeMaskFromCheckpoint {
		gen := ReadSeq(root, appendMode)
		if gen < 0 {
			gen = 0
		}
		return width + gen
	}
	if width < 1 {
		return 4096
	}
	return width
}
