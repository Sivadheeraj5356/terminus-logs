package ingest

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"os"
	"time"

	"greenhouse-fert-gate/internal/parse"
	"greenhouse-fert-gate/internal/profile"
	"greenhouse-fert-gate/internal/replay"
	"greenhouse-fert-gate/internal/store"
)

type Result struct {
	Skipped int
}

func IngestFile(st *store.Store, eventsPath, profilePath string) (*Result, error) {
	raw, err := os.ReadFile(eventsPath)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(raw)
	fileHash := hex.EncodeToString(sum[:])

	if ok, err := st.FindFileByHash(fileHash); err != nil {
		return nil, err
	} else if ok {
		return &Result{Skipped: 1}, nil
	}

	prof, err := profile.Load(profilePath)
	if err != nil {
		return nil, err
	}

	events, err := parse.DecodeAll(raw, prof)
	if err != nil {
		return nil, err
	}
	if len(events) == 0 {
		return nil, fmt.Errorf("empty file")
	}

	tx, err := st.Begin()
	if err != nil {
		return nil, err
	}
	defer func() { _ = tx.Rollback() }()

	var skipped int
	for _, ev := range events {
		eid := replay.EventID(ev)
		var n int
		if err := tx.QueryRow(
			"SELECT COUNT(*) FROM fertigation_events WHERE event_id=?",
			eid,
		).Scan(&n); err != nil {
			return nil, err
		}
		if n > 0 {
			skipped++
			continue
		}
		if err := applyEventTx(tx, prof, ev); err != nil {
			return nil, err
		}
		if _, err := tx.Exec(
			`INSERT INTO fertigation_events(event_id, zone_id, batch_id, event_seq, event_type, payload_json)
			 VALUES (?,?,?,?,?,?)`,
			eid, ev.ZoneID, ev.BatchID, ev.EventSeq, ev.EventType, string(ev.RawLine),
		); err != nil {
			return nil, err
		}
	}
	if err := store.RegisterFileTx(tx, fileHash, time.Now().Unix(), skipped); err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		return nil, err
	}
	return &Result{Skipped: skipped}, nil
}

func IngestFilePath(st *store.Store, eventsPath, profilePath string) error {
	_, err := IngestFile(st, eventsPath, profilePath)
	return err
}

func applyEventTx(tx *sql.Tx, prof *profile.Profile, ev *parse.Event) error {
	switch ev.EventType {
	case "ZONE_REGISTER":
		if !prof.ZoneAllowed(ev.ZoneID) {
			return fmt.Errorf("unknown zone")
		}
		return store.InsertZoneTx(tx, ev.ZoneID, ev.CropLabel)
	case "BATCH_OPEN":
		if !prof.ZoneAllowed(ev.ZoneID) {
			return fmt.Errorf("unknown zone")
		}
		var exists int
		if err := tx.QueryRow(
			"SELECT COUNT(*) FROM zones WHERE zone_id=?",
			ev.ZoneID,
		).Scan(&exists); err != nil {
			return err
		}
		if exists == 0 {
			return fmt.Errorf("unknown zone")
		}
		var openID sql.NullString
		if err := tx.QueryRow(
			"SELECT open_batch_id FROM zone_state WHERE zone_id=?",
			ev.ZoneID,
		).Scan(&openID); err == nil && openID.Valid && openID.String != "" {
			return fmt.Errorf("batch busy")
		}
		return store.InsertBatchTx(tx, ev.BatchID, ev.ZoneID, ev.OpenedAtUnix)
	case "DOSE_TICK":
		var status string
		if err := tx.QueryRow(
			"SELECT status FROM fertigation_batches WHERE batch_id=?",
			ev.BatchID,
		).Scan(&status); err != nil {
			return fmt.Errorf("batch not open")
		}
		if status != "OPEN" {
			return fmt.Errorf("batch not open")
		}
		var lastTs int64
		_ = tx.QueryRow(
			"SELECT COALESCE(MAX(recorded_at_unix), 0) FROM dose_events WHERE batch_id=?",
			ev.BatchID,
		).Scan(&lastTs)
		if lastTs > 0 && ev.RecordedAtUnix <= lastTs {
			return fmt.Errorf("non-increasing recorded_at")
		}
		doseID := fmt.Sprintf("%s-d%d", ev.BatchID, ev.EventSeq)
		return store.InsertDoseTx(tx, doseID, ev.BatchID, ev.ECmS, ev.Ph, ev.VolumeMl, ev.RecordedAtUnix)
	case "BATCH_CLOSE":
		var status string
		if err := tx.QueryRow(
			"SELECT status FROM fertigation_batches WHERE batch_id=?",
			ev.BatchID,
		).Scan(&status); err != nil {
			return fmt.Errorf("batch not open")
		}
		if status != "OPEN" {
			return fmt.Errorf("batch not open")
		}
		var doseCount int
		if err := tx.QueryRow(
			"SELECT COUNT(*) FROM dose_events WHERE batch_id=?",
			ev.BatchID,
		).Scan(&doseCount); err != nil {
			return err
		}
		if doseCount < prof.MinDoseCount {
			return fmt.Errorf("insufficient doses")
		}
		return store.CloseBatchTx(tx, ev.BatchID, ev.ClosedAtUnix)
	default:
		return fmt.Errorf("unknown event")
	}
}
