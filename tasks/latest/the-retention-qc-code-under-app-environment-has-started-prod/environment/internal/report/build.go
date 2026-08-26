package report

import (
	"errors"
	"sort"

	"ra.local/field/b7/holt"
	"ra.local/field/c4/vox"
	"ra.local/field/internal/basis"
	"ra.local/field/internal/domain"
	"ra.local/field/internal/intake"
	"ra.local/field/t8/nix"
)

func Build(root string, holdout string, target float64) (*domain.Attestation, error) {
	rows, sources, err := intake.Read(root)
	if err != nil {
		return nil, err
	}
	rows, runs := intake.Rank(rows)
	runIDs := make([]string, 0, len(runs))
	known := false
	for _, run := range runs {
		runIDs = append(runIDs, run.Run)
		if run.Run == holdout {
			known = true
		}
	}
	if len(runIDs) < 2 {
		return nil, errors.New("at least two runs are required")
	}
	if holdout != "" && !known {
		return nil, errors.New("unknown holdout run")
	}
	full := basis.Fit(rows, runIDs)
	selectedRuns := append([]string(nil), runIDs...)
	if holdout != "" {
		full, selectedRuns = fitSelected(rows, holdout)
	}
	full.TrainingRuns = append([]string(nil), selectedRuns...)

	targets := append([]string(nil), runIDs...)
	if holdout != "" {
		targets = []string{holdout}
	}
	sort.Strings(targets)
	shelf := holt.NewShelf()
	replays := make([]domain.Replay, 0, len(targets))
	views := make([]domain.SelectedView, 0, len(targets))
	for _, targetRun := range targets {
		replay, view, replayErr := vox.Traverse(rows, targetRun, target, full, shelf)
		if replayErr != nil {
			return nil, replayErr
		}
		replays = append(replays, replay)
		views = append(views, view)
	}
	doc := &domain.Attestation{
		SchemaVersion: "retention-attestation/3", CoverageTarget: target,
		Sources: sources, Observations: rows, Runs: runs, Model: full,
		Replays: replays,
		Lineage: domain.Lineage{SelectedViews: views, CacheEntries: shelf.Entries()},
	}
	if err := nix.Close(doc); err != nil {
		return nil, err
	}
	return doc, nil
}
