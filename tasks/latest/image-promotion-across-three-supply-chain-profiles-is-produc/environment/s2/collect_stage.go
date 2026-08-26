package s2

import (
	"fmt"
	"os"
	"path/filepath"

	"kvlab/internal/active"
	"kvlab/internal/export"
	"kvlab/internal/lane"
	"kvlab/internal/row"
	"kvlab/internal/seal"
	"kvlab/internal/session"
	"kvlab/internal/stage"
)

func laneReady(lf lane.File) bool {
	return lf.Stage.PullDigest != "" && lf.Stage.WalkDigest != ""
}

func collectExpiry(view active.View) int64 {
	return view.Prof.Expiry
}

func appendRun(sess session.File, runRow row.RunRow) session.File {
	sess.Profiles = row.MergeProfiles(sess.Profiles, runRow.Profile)
	sess.Runs = append(sess.Runs, runRow)
	return sess
}

func Collect(root, profile, outPath string) error {
	lf, err := lane.Load(root, profile)
	if err != nil {
		return err
	}
	if !laneReady(lf) {
		return fmt.Errorf("incomplete stage lane for %s", profile)
	}
	if err := lane.ValidateQuorum(lf); err != nil {
		return err
	}
	view, err := active.Resolve(root, profile, lf.Stage.PullStepIdx)
	if err != nil {
		return err
	}
	if !seal.ConfirmWalkRole(root, view, lf.Stage.WalkVersion) {
		return fmt.Errorf("walk role does not match active step for %s", profile)
	}

	transcript := stage.AssembleTranscript(lf)

	lf.RunSeq++
	runRow := row.RunRow{
		Profile:            profile,
		RunIndex:           lf.RunSeq - 1,
		RoleVersion:        lf.Stage.WalkVersion,
		ContentDigest:      lf.Stage.PullDigest,
		DelegationExpiry:   collectExpiry(view),
		StageTranscriptHex: transcript,
	}
	_ = lane.Save(root, lf)

	sess, _ := session.Load(root)
	sess = appendRun(sess, runRow)
	_ = session.Save(root, sess)

	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	f, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer f.Close()
	return export.Rollup(sess.Runs, f)
}
