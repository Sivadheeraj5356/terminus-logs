package journal

import (
	"path/filepath"

	"zonepub/internal/fsutil"
	"zonepub/internal/manifest"
)

type RecoveryDecision struct {
	ResumeEpoch string
	SkipSign    bool
	PromoteOnly bool
}

type RecoveryContext struct {
	Workspace string
	OutputDir string
	Records   []Record
}

// Classify inspects workspace state after interruption.
func Classify(ctx RecoveryContext) (RecoveryDecision, error) {
	if len(ctx.Records) == 0 {
		return RecoveryDecision{}, nil
	}
	last := ctx.Records[len(ctx.Records)-1]
	if last.Phase == PhaseStaged {
		return RecoveryDecision{ResumeEpoch: last.EpochID}, nil
	}
	staging := filepath.Join(ctx.Workspace, "staging", "pending-epoch")
	if fsutil.Exists(staging) {
		return RecoveryDecision{ResumeEpoch: last.EpochID}, nil
	}
	outZone := filepath.Join(ctx.OutputDir, "example.test.signed")
	if fsutil.Exists(outZone) {
		return RecoveryDecision{ResumeEpoch: last.EpochID, SkipSign: true}, nil
	}
	return RecoveryDecision{}, nil
}

func LoadCommitRecord(dir string) (*manifest.CommitRecord, error) {
	path := filepath.Join(dir, "commit-record.json")
	if !fsutil.Exists(path) {
		return nil, nil
	}
	return manifest.ReadCommitRecord(path)
}
