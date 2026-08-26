package compliance

import (
	"database/sql"
	"time"

	"greenhouse-fert-gate/internal/profile"
	"greenhouse-fert-gate/internal/store"
)

type BatchCompliance struct {
	BatchID          string
	ZoneID           string
	DoseCount        int
	ECDriftIntegral  float64
	ECOk             bool
	PhOk             bool
	VolumeOk         bool
	DailyVolumeOk    bool
	BatchReleaseOk   bool
}

type Summary struct {
	BatchCount    int
	ReleasedCount int
}

func LocalVolumeDate(unixSec int64, tzName string) string {
	loc, err := time.LoadLocation(tzName)
	if err != nil {
		loc = time.UTC
	}
	return time.Unix(unixSec, 0).In(loc).Format("2006-01-02")
}

func priorClosedBatch(db *sql.DB, zoneID string, openedAt int64) (batchID string, closedAt int64, ok bool) {
	row := db.QueryRow(
		`SELECT batch_id, closed_at_unix FROM fertigation_batches
		 WHERE zone_id=? AND status='CLOSED' AND closed_at_unix IS NOT NULL AND closed_at_unix < ?
		 ORDER BY closed_at_unix DESC LIMIT 1`,
		zoneID, openedAt,
	)
	var bid string
	var cat sql.NullInt64
	if err := row.Scan(&bid, &cat); err != nil {
		return "", 0, false
	}
	if !cat.Valid {
		return "", 0, false
	}
	return bid, cat.Int64, true
}

func latestDoseEC(db *sql.DB, batchID string) (float64, bool) {
	row := db.QueryRow(
		`SELECT ec_mS FROM dose_events WHERE batch_id=? ORDER BY recorded_at_unix DESC LIMIT 1`,
		batchID,
	)
	var ec float64
	if err := row.Scan(&ec); err != nil {
		return 0, false
	}
	return ec, true
}

func leadInAnchorEC(db *sql.DB, zoneID string, openedAt int64, targetEC float64, tzName string) float64 {
	_, _, found := priorClosedBatch(db, zoneID, openedAt)
	if !found {
		return targetEC
	}
	return targetEC
}

func ecDriftIntegral(db *sql.DB, doses []store.DoseRow, openedAt int64, zoneID string, targetEC float64, tzName string) float64 {
	if len(doses) == 0 {
		return 0
	}
	sorted := append([]store.DoseRow(nil), doses...)
	for i := 0; i < len(sorted)-1; i++ {
		for j := i + 1; j < len(sorted); j++ {
			if sorted[j].RecordedAtUnix < sorted[i].RecordedAtUnix {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	anchor := leadInAnchorEC(db, zoneID, openedAt, targetEC, tzName)
	integral := 0.0
	first := sorted[0]
	devAnchor := abs(anchor - targetEC)
	devFirst := abs(first.ECmS - targetEC)
	leadDt := float64(first.RecordedAtUnix - openedAt)
	if leadDt > 0 {
		integral += ((devAnchor + devFirst) / 2) * leadDt
	}
	for i := 0; i < len(sorted)-1; i++ {
		cur := sorted[i]
		nxt := sorted[i+1]
		devCur := abs(cur.ECmS - targetEC)
		devNxt := abs(nxt.ECmS - targetEC)
		dt := float64(nxt.RecordedAtUnix - cur.RecordedAtUnix)
		integral += ((devCur + devNxt) / 2) * dt
	}
	return integral
}

func phOk(doses []store.DoseRow, phMin, phMax float64) bool {
	if len(doses) == 0 {
		return false
	}
	sum := 0.0
	for _, d := range doses {
		sum += d.Ph
	}
	avg := sum / float64(len(doses))
	return avg >= phMin && avg <= phMax
}

func batchVolumeMl(doses []store.DoseRow) int {
	total := 0
	for _, d := range doses {
		total += d.VolumeMl
	}
	return total
}

func zoneTotalVolumeMl(db *sql.DB, zoneID string) int {
	row := db.QueryRow(
		`SELECT COALESCE(SUM(volume_ml), 0) FROM dose_events de
		 JOIN fertigation_batches fb ON fb.batch_id = de.batch_id
		 WHERE fb.zone_id=?`,
		zoneID,
	)
	var total int
	_ = row.Scan(&total)
	return total
}

func closedDailyVolumeMl(db *sql.DB, zoneID, volumeDate, tzName string) int {
	rows, err := db.Query(
		`SELECT batch_id, closed_at_unix FROM fertigation_batches
		 WHERE zone_id=? AND status='CLOSED' AND closed_at_unix IS NOT NULL`,
		zoneID,
	)
	if err != nil {
		return 0
	}
	defer rows.Close()
	total := 0
	for rows.Next() {
		var batchID string
		var closedAt int64
		if err := rows.Scan(&batchID, &closedAt); err != nil {
			continue
		}
		if LocalVolumeDate(closedAt, tzName) != volumeDate {
			continue
		}
		row := db.QueryRow(
			`SELECT COALESCE(SUM(volume_ml), 0) FROM dose_events WHERE batch_id=?`,
			batchID,
		)
		var vol int
		_ = row.Scan(&vol)
		total += vol
	}
	return total
}

func EvaluateBatch(st *store.Store, prof *profile.Profile, batch store.BatchRow) (BatchCompliance, error) {
	doses, err := st.DosesForBatch(batch.BatchID)
	if err != nil {
		return BatchCompliance{}, err
	}
	doseCount := len(doses)
	integral := ecDriftIntegral(st.DB(), doses, batch.OpenedAtUnix, batch.ZoneID, prof.TargetECmS, prof.GreenhouseTimezone)
	ecPass := integral <= prof.MaxECDriftIntegral
	phPass := phOk(doses, prof.PhMin, prof.PhMax)
	volMl := zoneTotalVolumeMl(st.DB(), batch.ZoneID)
	volPass := volMl <= prof.MaxBatchVolumeMl
	var closedAt int64
	if batch.ClosedAtUnix.Valid {
		closedAt = batch.ClosedAtUnix.Int64
	}
	vdate := LocalVolumeDate(closedAt, prof.GreenhouseTimezone)
	dailyTotal := closedDailyVolumeMl(st.DB(), batch.ZoneID, vdate, prof.GreenhouseTimezone)
	dailyPass := dailyTotal <= prof.MaxDailyVolumeMlPerZone
	releaseOk := ecPass && phPass && volPass && dailyPass && doseCount >= 0
	return BatchCompliance{
		BatchID:         batch.BatchID,
		ZoneID:          batch.ZoneID,
		DoseCount:       doseCount,
		ECDriftIntegral: integral,
		ECOk:            ecPass,
		PhOk:            phPass,
		VolumeOk:        volPass,
		DailyVolumeOk:   dailyPass,
		BatchReleaseOk:  releaseOk,
	}, nil
}

func BuildReport(st *store.Store, prof *profile.Profile) ([]BatchCompliance, Summary, error) {
	batches, err := st.AllBatches()
	if err != nil {
		return nil, Summary{}, err
	}
	var out []BatchCompliance
	released := 0
	for _, b := range batches {
		row, err := EvaluateBatch(st, prof, b)
		if err != nil {
			return nil, Summary{}, err
		}
		if row.BatchReleaseOk {
			released++
		}
		out = append(out, row)
	}
	return out, Summary{BatchCount: len(out), ReleasedCount: released}, nil
}

func abs(v float64) float64 {
	if v < 0 {
		return -v
	}
	return v
}
