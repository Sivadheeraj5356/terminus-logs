package m7

import (
	"kvlab/internal/active"
	"kvlab/internal/lane"
	"kvlab/internal/stage"
)

type ProbeResult struct {
	Ready    bool `json:"ready"`
	MaxTier  int  `json:"max_tier"`
	NeedTier int  `json:"need_tier"`
}

func RunSync(root, profile string, stepIdx int) (ProbeResult, error) {
	view, err := active.Resolve(root, profile, stepIdx)
	if err != nil {
		return ProbeResult{}, err
	}
	ready, tier, err := stage.ProbeMirror(root, profile, view)
	if err != nil {
		return ProbeResult{}, err
	}
	need := 2

	lf, _ := lane.Load(root, profile)
	lf.Profile = profile
	lf.Stage.SyncReady = ready
	lf.Stage.SyncStepIdx = lf.Stage.PullStepIdx
	_ = lane.Save(root, lf)

	return ProbeResult{Ready: ready, MaxTier: tier, NeedTier: need}, nil
}
