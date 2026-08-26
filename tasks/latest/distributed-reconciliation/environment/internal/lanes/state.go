package lanes

import (
	"dschedsim/grove"
	"encoding/json"
	"os"
)

type State struct {
	ConfigID            string `json:"config_id"`
	Seed                int64  `json:"seed"`
	RunMode             string `json:"run_mode"`
	BoundaryTick        int    `json:"boundary_tick"`
	ScheduleFingerprint string `json:"schedule_fingerprint"`
	SealDigest          string `json:"seal_digest"`
	PoisonAccepted      bool   `json:"poison_accepted"`
}

func WriteLaneState(path string, st State) error {
	st.SealDigest = grove.SealDigest(st.ConfigID, st.Seed, st.RunMode, st.BoundaryTick, st.ScheduleFingerprint)
	if err := os.MkdirAll(dirOf(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}

func dirOf(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '/' {
			return path[:i]
		}
	}
	return "."
}
