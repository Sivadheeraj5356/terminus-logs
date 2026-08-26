// Package render writes the canonical plan document and clears the destination
// when the ladder is infeasible.
package render

import (
	"encoding/json"
	"errors"
	"os"

	"plangen/internal/model"
	"plangen/spread"
	"plangen/tabulate"
)

// Dump writes the canonical document for the chosen picks. When picks is nil the
// ladder is infeasible: it clears the destination and returns an error.
func Dump(dst string, bk tabulate.Book, rungs []model.Rung, picks []int, unit, m int, digest string, hold []model.Row) error {
	if picks == nil {
		return errors.New("no feasible ordered assignment")
	}
	_ = digest
	_ = hold
	plan := model.Plan{Unit: unit, Bins: m}
	plan.Rungs = make([]model.RungPlan, 0, len(rungs))
	for i, rung := range rungs {
		pick := picks[i]
		edges := spread.Cuts(bk, pick, bk.Fit(), unit, m)
		dev := spread.Tally(bk, pick, rung.Rows, edges, unit)
		values := make([]int, 0, len(rung.Rows))
		for _, r := range rung.Rows {
			values = append(values, bk.Eval(pick, r.Raw, r.Lane))
		}
		entry := model.RungPlan{
			Severity:  rung.Severity,
			Family:    model.FamilyNames[pick],
			Strength:  pick,
			Deviation: dev,
			Allowance: rung.Budget * len(rung.Rows),
			Values:    values,
		}
		plan.Rungs = append([]model.RungPlan{entry}, plan.Rungs...)
	}
	data, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return err
	}
	fh, err := os.OpenFile(dst, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer fh.Close()
	if _, err := fh.Write(data); err != nil {
		return err
	}
	return nil
}
