package db

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func sqlite3(dbPath string, sql string) (string, error) {
	cmd := exec.Command("sqlite3", dbPath, sql)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		if stderr.Len() > 0 {
			return "", fmt.Errorf("%w: %s", err, stderr.String())
		}
		return "", err
	}
	return strings.TrimSpace(stdout.String()), nil
}

func Exec(dbPath, sql string) error {
	_, err := sqlite3(dbPath, sql)
	return err
}

func QueryOne(dbPath, sql string) (string, error) {
	out, err := sqlite3(dbPath, sql)
	if err != nil {
		return "", err
	}
	return out, nil
}

func InitSchema(dbPath string) error {
	if err := os.MkdirAll(filepathDir(dbPath), 0o755); err != nil {
		return err
	}
	schema := `
CREATE TABLE IF NOT EXISTS pins (
  path TEXT NOT NULL,
  version TEXT NOT NULL,
  goos TEXT NOT NULL,
  goarch TEXT NOT NULL,
  policy_revision TEXT NOT NULL,
  decision TEXT NOT NULL,
  PRIMARY KEY (path, goos, goarch, policy_revision)
);
CREATE TABLE IF NOT EXISTS decision_cache (
  path TEXT NOT NULL,
  version TEXT NOT NULL,
  goos TEXT NOT NULL,
  goarch TEXT NOT NULL,
  policy_revision TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (path, version, goos, goarch, policy_revision)
);
CREATE TABLE IF NOT EXISTS index_meta (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  policy_revision TEXT NOT NULL,
  index_complete INTEGER NOT NULL,
  write_epoch INTEGER NOT NULL
);
`
	return Exec(dbPath, schema)
}

func filepathDir(path string) string {
	i := strings.LastIndex(path, "/")
	if i < 0 {
		return "."
	}
	return path[:i]
}

func Escape(s string) string {
	return strings.ReplaceAll(s, "'", "''")
}
