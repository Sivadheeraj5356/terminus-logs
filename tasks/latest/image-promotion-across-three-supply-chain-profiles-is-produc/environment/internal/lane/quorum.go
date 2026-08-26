package lane

import "fmt"

func ValidateQuorum(lf File) error {
	if lf.Stage.PullDigest == "" || lf.Stage.WalkDigest == "" || lf.Stage.AdmitDigest == "" {
		return fmt.Errorf("incomplete stage lane for %s", lf.Profile)
	}
	if lf.Stage.PullStepIdx != lf.Stage.WalkStepIdx {
		return fmt.Errorf("step mismatch: pull=%d walk=%d", lf.Stage.PullStepIdx, lf.Stage.WalkStepIdx)
	}
	return nil
}
