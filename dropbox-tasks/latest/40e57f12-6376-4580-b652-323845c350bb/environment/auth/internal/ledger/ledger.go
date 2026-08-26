package ledger

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"

	_ "github.com/mattn/go-sqlite3"

	"github.com/acme/auth/internal/clock"
)

type Ledger struct {
	db    *sql.DB
	clock *clock.Clock
}

const schema = `
CREATE TABLE IF NOT EXISTS revocations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  jti TEXT NOT NULL,
  revoked_at TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_revocations_jti ON revocations(jti);
`

func Open(dbPath string, clk *clock.Clock) (*Ledger, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0o755); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, err
	}
	return &Ledger{db: db, clock: clk}, nil
}

func (l *Ledger) Close() error {
	return l.db.Close()
}

// Revoke marks a token revoked using an upsert-style update path.
func (l *Ledger) Revoke(jti, reason string) error {
	ts := time.Now().UTC().Format(time.RFC3339)
	res, err := l.db.Exec(
		`UPDATE revocations SET revoked_at = ?, reason = ? WHERE jti = ?`,
		ts, reason, jti,
	)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		_, err = l.db.Exec(
			`INSERT INTO revocations (jti, revoked_at, reason) VALUES (?, ?, ?)`,
			jti, ts, reason,
		)
	}
	return err
}

func (l *Ledger) IsRevoked(jti string) (bool, error) {
	var count int
	err := l.db.QueryRow(`SELECT count(*) FROM revocations WHERE jti = ?`, jti).Scan(&count)
	if err != nil {
		return false, err
	}
	return count > 0, nil
}

func (l *Ledger) RowsForJTI(jti string) ([]map[string]string, error) {
	rows, err := l.db.Query(
		`SELECT id, jti, revoked_at, reason FROM revocations WHERE jti = ? ORDER BY id`,
		jti,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]string{}
	for rows.Next() {
		var id int
		var j, ts, reason string
		if err := rows.Scan(&id, &j, &ts, &reason); err != nil {
			return nil, err
		}
		out = append(out, map[string]string{
			"id":         fmt.Sprintf("%d", id),
			"jti":        j,
			"revoked_at": ts,
			"reason":     reason,
		})
	}
	return out, rows.Err()
}

func (l *Ledger) RowCount() (int, error) {
	var n int
	err := l.db.QueryRow(`SELECT count(*) FROM revocations`).Scan(&n)
	return n, err
}

func (l *Ledger) ListRevokedJTIs() ([]string, error) {
	rows, err := l.db.Query(`SELECT jti FROM revocations ORDER BY jti ASC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var jti string
		if err := rows.Scan(&jti); err != nil {
			return nil, err
		}
		out = append(out, jti)
	}
	return out, rows.Err()
}
