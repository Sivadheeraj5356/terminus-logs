package store

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

type Store struct {
	db *sql.DB
}

type BatchRow struct {
	BatchID      string
	ZoneID       string
	OpenedAtUnix int64
	ClosedAtUnix sql.NullInt64
	Status       string
}

type DoseRow struct {
	DoseID           string
	BatchID          string
	ECmS             float64
	Ph               float64
	VolumeMl         int
	RecordedAtUnix   int64
}

func Open(path string) (*Store, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite3", path+"?_foreign_keys=on")
	if err != nil {
		return nil, err
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) DB() *sql.DB {
	return s.db
}

func (s *Store) Begin() (*sql.Tx, error) {
	return s.db.Begin()
}

func (s *Store) Migrate(migrationsDir string) error {
	entries, err := os.ReadDir(migrationsDir)
	if err != nil {
		return err
	}
	var files []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".sql") {
			files = append(files, e.Name())
		}
	}
	sort.Strings(files)
	for i, name := range files {
		want := i + 1
		var have int
		_ = s.db.QueryRow("SELECT COALESCE(MAX(version),0) FROM schema_migrations").Scan(&have)
		if have >= want {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(migrationsDir, name))
		if err != nil {
			return err
		}
		if _, err := s.db.Exec(string(raw)); err != nil {
			return fmt.Errorf("migration %s: %w", name, err)
		}
		if _, err := s.db.Exec("INSERT INTO schema_migrations(version) VALUES (?)", want); err != nil {
			return err
		}
	}
	return nil
}

func (s *Store) FindFileByHash(hash string) (bool, error) {
	var n int
	err := s.db.QueryRow("SELECT COUNT(*) FROM ingest_files WHERE file_hash=?", hash).Scan(&n)
	return n > 0, err
}

func (s *Store) RegisterFile(hash string, ingestedAt int64, duplicateSkipped int) error {
	_, err := s.db.Exec(
		"INSERT INTO ingest_files(file_hash, ingested_at_unix, duplicate_skipped) VALUES (?,?,?)",
		hash, ingestedAt, duplicateSkipped,
	)
	return err
}

func (s *Store) ZoneExists(zoneID string) (bool, error) {
	var n int
	err := s.db.QueryRow("SELECT COUNT(*) FROM zones WHERE zone_id=?", zoneID).Scan(&n)
	return n > 0, err
}

func (s *Store) InsertZone(zoneID, cropLabel string) error {
	_, err := s.db.Exec(
		"INSERT OR IGNORE INTO zones(zone_id, crop_label) VALUES (?,?)",
		zoneID, cropLabel,
	)
	return err
}

func (s *Store) OpenBatchID(zoneID string) (string, error) {
	var bid sql.NullString
	err := s.db.QueryRow(
		"SELECT open_batch_id FROM zone_state WHERE zone_id=?",
		zoneID,
	).Scan(&bid)
	if err == sql.ErrNoRows {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if !bid.Valid {
		return "", nil
	}
	return bid.String, nil
}

func (s *Store) BatchStatus(batchID string) (string, error) {
	var status string
	err := s.db.QueryRow(
		"SELECT status FROM fertigation_batches WHERE batch_id=?",
		batchID,
	).Scan(&status)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return status, err
}

func (s *Store) InsertBatch(batchID, zoneID string, openedAt int64) error {
	_, err := s.db.Exec(
		`INSERT INTO fertigation_batches(batch_id, zone_id, opened_at_unix, status)
		 VALUES (?, ?, ?, 'OPEN')`,
		batchID, zoneID, openedAt,
	)
	if err != nil {
		return err
	}
	_, err = s.db.Exec(
		`INSERT INTO zone_state(zone_id, open_batch_id) VALUES (?, ?)
		 ON CONFLICT(zone_id) DO UPDATE SET open_batch_id=excluded.open_batch_id`,
		zoneID, batchID,
	)
	return err
}

func (s *Store) CloseBatch(batchID string, closedAt int64) error {
	_, err := s.db.Exec(
		`UPDATE fertigation_batches SET status='CLOSED', closed_at_unix=? WHERE batch_id=?`,
		closedAt, batchID,
	)
	if err != nil {
		return err
	}
	var zoneID string
	if err := s.db.QueryRow(
		"SELECT zone_id FROM fertigation_batches WHERE batch_id=?",
		batchID,
	).Scan(&zoneID); err != nil {
		return err
	}
	_, err = s.db.Exec(
		"UPDATE zone_state SET open_batch_id=NULL WHERE zone_id=?",
		zoneID,
	)
	return err
}

func (s *Store) DoseCount(batchID string) (int, error) {
	var n int
	err := s.db.QueryRow(
		"SELECT COUNT(*) FROM dose_events WHERE batch_id=?",
		batchID,
	).Scan(&n)
	return n, err
}

func (s *Store) LastDoseRecordedAt(batchID string) (int64, error) {
	var ts sql.NullInt64
	err := s.db.QueryRow(
		"SELECT MAX(recorded_at_unix) FROM dose_events WHERE batch_id=?",
		batchID,
	).Scan(&ts)
	if err != nil || !ts.Valid {
		return 0, err
	}
	return ts.Int64, nil
}

func (s *Store) InsertDose(doseID, batchID string, ec, ph float64, volume int, recordedAt int64) error {
	_, err := s.db.Exec(
		`INSERT INTO dose_events(dose_id, batch_id, ec_mS, ph, volume_ml, recorded_at_unix)
		 VALUES (?, ?, ?, ?, ?, ?)`,
		doseID, batchID, ec, ph, volume, recordedAt,
	)
	return err
}

func (s *Store) AddDailyVolume(zoneID, volumeDate string, volume int) error {
	_, err := s.db.Exec(
		`INSERT INTO daily_zone_volume(zone_id, volume_date, volume_ml) VALUES (?,?,?)
		 ON CONFLICT(zone_id, volume_date) DO UPDATE SET volume_ml = volume_ml + excluded.volume_ml`,
		zoneID, volumeDate, volume,
	)
	return err
}

func (s *Store) ClosedBatches() ([]BatchRow, error) {
	rows, err := s.db.Query(
		`SELECT batch_id, zone_id, opened_at_unix, closed_at_unix, status
		 FROM fertigation_batches WHERE status='CLOSED' ORDER BY batch_id ASC`,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []BatchRow
	for rows.Next() {
		var r BatchRow
		if err := rows.Scan(&r.BatchID, &r.ZoneID, &r.OpenedAtUnix, &r.ClosedAtUnix, &r.Status); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) AllBatches() ([]BatchRow, error) {
	rows, err := s.db.Query(
		`SELECT batch_id, zone_id, opened_at_unix, closed_at_unix, status
		 FROM fertigation_batches ORDER BY batch_id ASC`,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []BatchRow
	for rows.Next() {
		var r BatchRow
		if err := rows.Scan(&r.BatchID, &r.ZoneID, &r.OpenedAtUnix, &r.ClosedAtUnix, &r.Status); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) DosesForBatch(batchID string) ([]DoseRow, error) {
	rows, err := s.db.Query(
		`SELECT dose_id, batch_id, ec_mS, ph, volume_ml, recorded_at_unix
		 FROM dose_events WHERE batch_id=? ORDER BY recorded_at_unix ASC`,
		batchID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []DoseRow
	for rows.Next() {
		var r DoseRow
		if err := rows.Scan(&r.DoseID, &r.BatchID, &r.ECmS, &r.Ph, &r.VolumeMl, &r.RecordedAtUnix); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) EventExists(eventID string) (bool, error) {
	var n int
	err := s.db.QueryRow(
		"SELECT COUNT(*) FROM fertigation_events WHERE event_id=?",
		eventID,
	).Scan(&n)
	return n > 0, err
}

func (s *Store) InsertEvent(eventID, zoneID, batchID, eventType, payload string, eventSeq int) error {
	_, err := s.db.Exec(
		`INSERT INTO fertigation_events(event_id, zone_id, batch_id, event_seq, event_type, payload_json)
		 VALUES (?,?,?,?,?,?)`,
		eventID, zoneID, batchID, eventSeq, eventType, payload,
	)
	return err
}

func InsertZoneTx(tx *sql.Tx, zoneID, cropLabel string) error {
	_, err := tx.Exec(
		"INSERT OR IGNORE INTO zones(zone_id, crop_label) VALUES (?,?)",
		zoneID, cropLabel,
	)
	return err
}

func InsertBatchTx(tx *sql.Tx, batchID, zoneID string, openedAt int64) error {
	_, err := tx.Exec(
		`INSERT INTO fertigation_batches(batch_id, zone_id, opened_at_unix, status)
		 VALUES (?, ?, ?, 'OPEN')`,
		batchID, zoneID, openedAt,
	)
	if err != nil {
		return err
	}
	_, err = tx.Exec(
		`INSERT INTO zone_state(zone_id, open_batch_id) VALUES (?, ?)
		 ON CONFLICT(zone_id) DO UPDATE SET open_batch_id=excluded.open_batch_id`,
		zoneID, batchID,
	)
	return err
}

func InsertDoseTx(tx *sql.Tx, doseID, batchID string, ec, ph float64, volume int, recordedAt int64) error {
	_, err := tx.Exec(
		`INSERT INTO dose_events(dose_id, batch_id, ec_mS, ph, volume_ml, recorded_at_unix)
		 VALUES (?, ?, ?, ?, ?, ?)`,
		doseID, batchID, ec, ph, volume, recordedAt,
	)
	return err
}

func CloseBatchTx(tx *sql.Tx, batchID string, closedAt int64) error {
	_, err := tx.Exec(
		`UPDATE fertigation_batches SET status='CLOSED', closed_at_unix=? WHERE batch_id=?`,
		closedAt, batchID,
	)
	if err != nil {
		return err
	}
	var zoneID string
	if err := tx.QueryRow(
		"SELECT zone_id FROM fertigation_batches WHERE batch_id=?",
		batchID,
	).Scan(&zoneID); err != nil {
		return err
	}
	_, err = tx.Exec(
		"UPDATE zone_state SET open_batch_id=NULL WHERE zone_id=?",
		zoneID,
	)
	return err
}

func RegisterFileTx(tx *sql.Tx, hash string, ingestedAt int64, duplicateSkipped int) error {
	_, err := tx.Exec(
		"INSERT INTO ingest_files(file_hash, ingested_at_unix, duplicate_skipped) VALUES (?,?,?)",
		hash, ingestedAt, duplicateSkipped,
	)
	return err
}
