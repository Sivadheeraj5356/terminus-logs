package ingest

import (
	"bufio"
	"bytes"
	"crypto/sha256"
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

	var skipped int
	scanner := bufio.NewScanner(bytes.NewReader(raw))
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		ev, err := parse.ParseLine(line, prof)
		if err != nil {
			return nil, err
		}
		eid := replay.EventID(ev)
		skip, err := replay.ShouldSkip(st, eid)
		if err != nil {
			return nil, err
		}
		if skip {
			skipped++
			continue
		}
		if err := applyEvent(st, prof, ev); err != nil {
			return nil, err
		}
		if err := st.InsertEvent(eid, ev.ZoneID, ev.BatchID, ev.EventType, string(ev.RawLine), ev.EventSeq); err != nil {
			return nil, err
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	_ = st.RegisterFile(fileHash, time.Now().Unix(), skipped)
	return &Result{Skipped: skipped}, nil
}

func IngestFilePath(st *store.Store, eventsPath, profilePath string) error {
	_, err := IngestFile(st, eventsPath, profilePath)
	return err
}

func applyEvent(st *store.Store, prof *profile.Profile, ev *parse.Event) error {
	switch ev.EventType {
	case "ZONE_REGISTER":
		if !prof.ZoneAllowed(ev.ZoneID) {
			return fmt.Errorf("unknown zone")
		}
		return st.InsertZone(ev.ZoneID, ev.CropLabel)
	case "BATCH_OPEN":
		if !prof.ZoneAllowed(ev.ZoneID) {
			return fmt.Errorf("unknown zone")
		}
		exists, err := st.ZoneExists(ev.ZoneID)
		if err != nil {
			return err
		}
		if !exists {
			return fmt.Errorf("unknown zone")
		}
		openID, err := st.OpenBatchID(ev.ZoneID)
		if err != nil {
			return err
		}
		if openID != "" {
			return fmt.Errorf("batch busy")
		}
		return st.InsertBatch(ev.BatchID, ev.ZoneID, ev.OpenedAtUnix)
	case "DOSE_TICK":
		status, err := st.BatchStatus(ev.BatchID)
		if err != nil {
			return err
		}
		if status != "OPEN" {
			return fmt.Errorf("batch not open")
		}
		doseID := fmt.Sprintf("%s-d%d", ev.BatchID, ev.EventSeq)
		if err := st.InsertDose(doseID, ev.BatchID, ev.ECmS, ev.Ph, ev.VolumeMl, ev.RecordedAtUnix); err != nil {
			return err
		}
		var zoneID string
		if err := st.DB().QueryRow(
			"SELECT zone_id FROM fertigation_batches WHERE batch_id=?",
			ev.BatchID,
		).Scan(&zoneID); err != nil {
			return err
		}
		vdate := complianceLocalDate(ev.RecordedAtUnix, prof.GreenhouseTimezone)
		return st.AddDailyVolume(zoneID, vdate, ev.VolumeMl)
	case "BATCH_CLOSE":
		status, err := st.BatchStatus(ev.BatchID)
		if err != nil {
			return err
		}
		if status != "OPEN" {
			return fmt.Errorf("batch not open")
		}
		return st.CloseBatch(ev.BatchID, ev.ClosedAtUnix)
	default:
		return fmt.Errorf("unknown event")
	}
}

func complianceLocalDate(unixSec int64, tzName string) string {
	loc, err := time.LoadLocation(tzName)
	if err != nil {
		loc = time.UTC
	}
	return time.Unix(unixSec, 0).In(loc).Format("2006-01-02")
}
