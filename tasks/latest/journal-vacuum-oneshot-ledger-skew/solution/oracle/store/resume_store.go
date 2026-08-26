package store

import (
	"encoding/json"
	"os"

	"burstverify/internal/spool"
)

type resumeRecord struct {
	FixtureLabel  string `json:"fixture_label"`
	ReaderEpoch   string `json:"reader_epoch"`
	ObservedBytes int    `json:"observed_bytes"`
}

func ApplyResume(path, label, reader string, ledger *spool.Ledger) error {
	if path == "" {
		return nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	var rec resumeRecord
	if err := json.Unmarshal(raw, &rec); err != nil {
		return err
	}
	if rec.FixtureLabel != label || rec.ReaderEpoch != reader {
		return nil
	}
	ledger.ObservedBytes += rec.ObservedBytes
	return nil
}
