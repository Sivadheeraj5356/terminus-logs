package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const dbPath = "/app/data/crosspay.db"

// sqliteExec runs one or more SQL statements against the DB file via the
// sqlite3 CLI and returns combined stdout, or an error.
func sqliteExec(sql string) (string, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		return "", fmt.Errorf("mkdir data: %w", err)
	}
	cmd := exec.Command("sqlite3", dbPath)
	cmd.Stdin = strings.NewReader(sql)
	out, err := cmd.Output()
	return strings.TrimRight(string(out), "\n"), err
}

// sqliteQuery runs a SELECT via sqlite3 with pipe-separated output and returns
// rows split by newline (empty slice when there are no rows).
func sqliteQuery(sql string) ([]string, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		return nil, fmt.Errorf("mkdir data: %w", err)
	}
	cmd := exec.Command("sqlite3", "-separator", "|", dbPath)
	cmd.Stdin = strings.NewReader(sql)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	raw := strings.TrimRight(string(out), "\n")
	if raw == "" {
		return []string{}, nil
	}
	return strings.Split(raw, "\n"), nil
}

// sqlQuote single-quotes a string value, escaping internal single-quotes.
func sqlQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "''") + "'"
}

// InitDB creates the schema from /app/schema.sql idempotently.
func InitDB() error {
	schemaBytes, err := os.ReadFile("/app/schema.sql")
	if err != nil {
		return fmt.Errorf("read schema.sql: %w", err)
	}
	_, err = sqliteExec(string(schemaBytes))
	return err
}
