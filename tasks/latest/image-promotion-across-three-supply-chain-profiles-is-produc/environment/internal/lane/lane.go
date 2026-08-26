package lane

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type StageSnap struct {
	PullDigest  string `json:"pull_digest"`
	SyncReady   bool   `json:"sync_ready"`
	WalkVersion int    `json:"walk_version"`
	WalkDigest  string `json:"walk_digest"`
	AdmitDigest string `json:"admit_digest"`
	PullStepIdx int    `json:"pull_step_idx"`
	SyncStepIdx int    `json:"sync_step_idx"`
	WalkStepIdx int    `json:"walk_step_idx"`
}

type File struct {
	Profile string    `json:"profile"`
	RunSeq  int       `json:"run_seq"`
	Stage   StageSnap `json:"stage"`
}

func Path(root, profile string) string {
	return filepath.Join(root, "..", "state", "lanes", profile+".json")
}

func Load(root, profile string) (File, error) {
	path := Path(root, profile)
	raw, err := os.ReadFile(path)
	if err != nil {
		return File{Profile: profile}, nil
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return File{}, err
	}
	return f, nil
}

func Save(root string, f File) error {
	path := Path(root, f.Profile)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(f)
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}
