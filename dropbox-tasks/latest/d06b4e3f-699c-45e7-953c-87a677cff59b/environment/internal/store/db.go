// Package store is the only part of chainaudit that touches SQLite directly.
package store

import (
	"database/sql"

	_ "modernc.org/sqlite"

	"chainaudit/internal/model"
)

type Store struct {
	db *sql.DB
}

func Open(path string) (*Store, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) Streams() ([]model.Stream, error) {
	rows, err := s.db.Query(`SELECT stream_id, migrated_at, checkpoint_interval, retention_days, legal_hold, created_at FROM streams ORDER BY stream_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []model.Stream
	for rows.Next() {
		var st model.Stream
		var migratedAt sql.NullInt64
		var legalHold int64
		if err := rows.Scan(&st.StreamID, &migratedAt, &st.CheckpointInterval, &st.RetentionDays, &legalHold, &st.CreatedAt); err != nil {
			return nil, err
		}
		if migratedAt.Valid {
			v := migratedAt.Int64
			st.MigratedAt = &v
		}
		st.LegalHold = legalHold != 0
		out = append(out, st)
	}
	return out, rows.Err()
}

func (s *Store) Events(streamID string) ([]model.Event, error) {
	rows, err := s.db.Query(`SELECT stream_id, seq, ts, event_type, payload, tombstone, legal_hold, leaf_hash FROM events WHERE stream_id = ? ORDER BY seq`, streamID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []model.Event
	for rows.Next() {
		var ev model.Event
		var tombstone, legalHold int64
		if err := rows.Scan(&ev.StreamID, &ev.Seq, &ev.Ts, &ev.EventType, &ev.Payload, &tombstone, &legalHold, &ev.LeafHash); err != nil {
			return nil, err
		}
		ev.Tombstone = tombstone != 0
		ev.LegalHold = legalHold != 0
		out = append(out, ev)
	}
	return out, rows.Err()
}

func (s *Store) Checkpoints(streamID string) ([]model.Checkpoint, error) {
	rows, err := s.db.Query(`SELECT stream_id, batch_index, start_seq, end_seq, merkle_root, signature, key_id, created_at FROM checkpoints WHERE stream_id = ? ORDER BY batch_index`, streamID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []model.Checkpoint
	for rows.Next() {
		var cp model.Checkpoint
		if err := rows.Scan(&cp.StreamID, &cp.BatchIndex, &cp.StartSeq, &cp.EndSeq, &cp.MerkleRoot, &cp.Signature, &cp.KeyID, &cp.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, cp)
	}
	return out, rows.Err()
}

// DeleteBatch removes every event row for stream between startSeq and endSeq
// inclusive, and returns how many rows were actually deleted (0 if the batch
// was already pruned by an earlier run).
func (s *Store) DeleteBatch(streamID string, startSeq, endSeq int64) (int64, error) {
	res, err := s.db.Exec(`DELETE FROM events WHERE stream_id = ? AND seq BETWEEN ? AND ?`, streamID, startSeq, endSeq)
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}
