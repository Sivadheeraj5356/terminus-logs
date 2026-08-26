package staging

import (
	"encoding/json"
	"os"
	"path/filepath"

	"passenger-rebooking-engine/internal/ingest"
	"passenger-rebooking-engine/internal/load"
	"passenger-rebooking-engine/internal/model"
	"passenger-rebooking-engine/internal/policy"
	"passenger-rebooking-engine/internal/util"
)

func snapshotFingerprint(snap model.RebookingSnapshot) string {
	body := map[string]any{
		"snapshot_version":             snap.SnapshotVersion,
		"snapshot_fingerprint":         "",
		"disruption_date":              snap.DisruptionDate,
		"collapsed_cancellation_count": snap.CollapsedCancellationCount,
		"auto_rebooked_passenger_ids":  snap.AutoRebookedPassengerIDs,
		"passenger_records":            snap.PassengerRecords,
		"remaining_seats":              snap.RemainingSeats,
		"cancelled_flights":            snap.CancelledFlights,
	}
	return util.Fingerprint(body)
}

func readLedger(path string) (*model.RebookingLedger, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var led model.RebookingLedger
	if err := json.Unmarshal(raw, &led); err != nil {
		return nil, err
	}
	return &led, nil
}

func writeJSON(path string, body any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(body, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}

func WriteStage(snap model.RebookingSnapshot, bundle *load.Bundle) error {
	snap.SnapshotFingerprint = snapshotFingerprint(snap)

	prev, err := readLedger(load.LedgerPath())
	if err != nil {
		return err
	}
	digest := ingest.InputDigest(bundle)
	seq := 1
	if prev != nil {
		seq = prev.StageSequence + 1
	}

	led := model.RebookingLedger{
		LedgerVersion:    1,
		InputDigest:      digest,
		StageSequence:    seq,
		PriorityPickMode: policy.PickMode(bundle.Policy),
		RemainingSeatMap: snap.RemainingSeats,
	}

	if err := writeJSON(load.SnapshotPath(), snap); err != nil {
		return err
	}
	return writeJSON(load.LedgerPath(), led)
}
