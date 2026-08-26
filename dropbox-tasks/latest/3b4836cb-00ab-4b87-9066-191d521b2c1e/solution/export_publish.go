package export

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"

	"passenger-rebooking-engine/internal/load"
	"passenger-rebooking-engine/internal/model"
	"passenger-rebooking-engine/internal/util"
)

var ErrSnapshotMissing = errors.New("rebooking snapshot missing")
var ErrLedgerMissing = errors.New("rebooking ledger missing")
func readSnapshot(path string) (*model.RebookingSnapshot, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var snap model.RebookingSnapshot
	if err := json.Unmarshal(raw, &snap); err != nil {
		return nil, err
	}
	return &snap, nil
}

func readLedger(path string) (*model.RebookingLedger, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var led model.RebookingLedger
	if err := json.Unmarshal(raw, &led); err != nil {
		return nil, err
	}
	return &led, nil
}

func planFingerprint(entries []model.PlanEntry) string {
	body := map[string]any{"entries": entries}
	return util.Fingerprint(body)
}

func writeJSON(path string, body any) error {
	raw, err := json.MarshalIndent(body, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}

func Publish() error {
	snapPath := load.SnapshotPath()
	ledPath := load.LedgerPath()

	snap, err := readSnapshot(snapPath)
	if err != nil {
		if os.IsNotExist(err) {
			return ErrSnapshotMissing
		}
		return err
	}
	led, err := readLedger(ledPath)
	if err != nil {
		if os.IsNotExist(err) {
			return ErrLedgerMissing
		}
		return err
	}

	entries := make([]model.PlanEntry, 0, len(snap.PassengerRecords))
	for i, rec := range snap.PassengerRecords {
		entries = append(entries, model.PlanEntry{
			PassengerID:   rec.PassengerID,
			Status:        rec.Status,
			PriorityScore: rec.PriorityScore,
			RebookedLegs:  rec.RebookedLegs,
			RebookRank:    i + 1,
		})
	}

	plan := model.RebookingPlan{
		PlanVersion:         1,
		LedgerStageSequence: led.StageSequence,
		Entries:             entries,
	}
	plan.PlanFingerprint = planFingerprint(entries)

	rebooked, standby, unaffected := 0, 0, 0
	for _, rec := range snap.PassengerRecords {
		switch rec.Status {
		case "rebooked":
			rebooked++
		case "standby":
			standby++
		default:
			unaffected++
		}
	}

	summary := model.PassengerSummary{
		SummaryVersion:      1,
		DisruptionDate:      snap.DisruptionDate,
		TotalPassengers:     len(snap.PassengerRecords),
		RebookedCount:       rebooked,
		StandbyCount:        standby,
		UnaffectedCount:     unaffected,
		PriorityPickMode:    led.PriorityPickMode,
		CancelledFlightList: snap.CancelledFlights,
	}

	if err := os.MkdirAll(filepath.Dir(load.PlanPath()), 0o755); err != nil {
		return err
	}
	if err := writeJSON(load.PlanPath(), plan); err != nil {
		return err
	}
	return writeJSON(load.SummaryPath(), summary)
}
