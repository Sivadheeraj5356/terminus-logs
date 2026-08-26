package driver

import (
	"path/filepath"

	"lab.local/salt_pond/internal/config"
	"lab.local/salt_pond/internal/engine"
	"lab.local/salt_pond/pkg/digest"
)

// Report is the outward JSON document.
type Report struct {
	SchemaVersion   string            `json:"schema_version"`
	PondID          string            `json:"pond_id"`
	MastEpoch       uint32            `json:"mast_epoch"`
	Arms            []engine.ArmRow   `json:"arms"`
	DailyFronts     []engine.DayFront `json:"daily_fronts"`
	CalmLatchEvents int               `json:"calm_latch_events"`
	SurveyMismatch  int               `json:"survey_mismatch"`
	FrontSum        int               `json:"front_sum"`
	DigestHex       string            `json:"digest_hex"`
}

// RunActive loads the active pond and returns a filled report.
func RunActive(appRoot string) (Report, error) {
	dir, err := config.ActiveDir(appRoot)
	if err != nil {
		return Report{}, err
	}
	bundle, err := config.LoadBundle(dir)
	if err != nil {
		return Report{}, err
	}
	out := engine.ReplayWith(bundle.Plan, bundle.Arms, bundle.Tape, bundle.Surveys, engine.ReplayOpts{
		AppRoot:    appRoot,
		ResumePath: filepath.Join(dir, "resume_state.json"),
	})
	dig := digest.Fold(
		bundle.Plan.PondID,
		out.MastEpoch,
		out.CalmLatchEvents,
		out.SurveyMismatch,
		out.FrontSum,
	)
	return Report{
		SchemaVersion:   "1",
		PondID:          bundle.Plan.PondID,
		MastEpoch:       out.MastEpoch,
		Arms:            out.Arms,
		DailyFronts:     out.DailyFronts,
		CalmLatchEvents: out.CalmLatchEvents,
		SurveyMismatch:  out.SurveyMismatch,
		FrontSum:        out.FrontSum,
		DigestHex:       dig,
	}, nil
}
