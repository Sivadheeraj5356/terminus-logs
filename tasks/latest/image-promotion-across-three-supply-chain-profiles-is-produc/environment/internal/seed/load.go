package seed

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Step struct {
	Idx           int    `json:"idx"`
	Label         string `json:"label"`
	MirrorTier    int    `json:"mirror_tier"`
	TargetsGen    int    `json:"targets_gen,omitempty"`
	Expiry        int64  `json:"expiry,omitempty"`
	AdmissionSnap string `json:"admission_snap,omitempty"`
	PullMode      int    `json:"pull_mode,omitempty"`
	WalkMode      int    `json:"walk_mode,omitempty"`
}

type Profile struct {
	ImageTag      string `json:"image_tag"`
	TargetsGen    int    `json:"targets_gen"`
	Expiry        int64  `json:"expiry"`
	ProxyRequired int    `json:"proxy_required"`
	WalkMode      int    `json:"walk_mode"`
	PullMode      int    `json:"pull_mode"`
	AdmissionSnap string `json:"admission_snap"`
	ReplicaFlip   bool   `json:"replica_flip"`
	Steps         []Step `json:"steps"`
}

func Load(root, profile string) (Profile, error) {
	path := filepath.Join(root, "fixtures", "seed", profile, "seed_steps.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return Profile{}, err
	}
	var p Profile
	if err := json.Unmarshal(raw, &p); err != nil {
		return Profile{}, err
	}
	return p, nil
}

func StepByIdx(p Profile, idx int) Step {
	for _, s := range p.Steps {
		if s.Idx == idx {
			return s
		}
	}
	if len(p.Steps) > 0 {
		return p.Steps[0]
	}
	return Step{Idx: idx, MirrorTier: 2}
}

func StepTargetsGen(p Profile, s Step) int {
	if s.TargetsGen > 0 {
		return s.TargetsGen
	}
	return p.TargetsGen
}

func StepExpiry(p Profile, s Step) int64 {
	if s.Expiry > 0 {
		return s.Expiry
	}
	return p.Expiry
}

func StepAdmission(p Profile, s Step) string {
	if s.AdmissionSnap != "" {
		return s.AdmissionSnap
	}
	return p.AdmissionSnap
}

func StepPullMode(p Profile, s Step) int {
	if s.PullMode != 0 {
		return s.PullMode
	}
	return p.PullMode
}

func StepWalkMode(p Profile, s Step) int {
	if s.WalkMode != 0 {
		return s.WalkMode
	}
	return p.WalkMode
}
