package active

import (
	"kvlab/internal/seed"
)

type View struct {
	Prof    seed.Profile
	Step    seed.Step
	StepIdx int
}

func Resolve(root, profile string, stepIdx int) (View, error) {
	prof, err := seed.Load(root, profile)
	if err != nil {
		return View{}, err
	}
	step := seed.StepByIdx(prof, stepIdx)
	return View{Prof: prof, Step: step, StepIdx: stepIdx}, nil
}

func (v View) TargetsGen() int {
	return seed.StepTargetsGen(v.Prof, v.Step)
}

func (v View) Expiry() int64 {
	return seed.StepExpiry(v.Prof, v.Step)
}

func (v View) Admission() string {
	return seed.StepAdmission(v.Prof, v.Step)
}

func (v View) PullMode() int {
	return seed.StepPullMode(v.Prof, v.Step)
}

func (v View) WalkMode() int {
	return seed.StepWalkMode(v.Prof, v.Step)
}

func (v View) WalkTransport() int {
	if v.Prof.ProxyRequired == 1 {
		return v.PullMode()
	}
	return v.WalkMode()
}

func (v View) MirrorTier(root string) int {
	tier := v.Step.MirrorTier
	if v.Prof.ReplicaFlip {
		// replica rewrite handled in stage/mirror
		return tier
	}
	return tier
}
