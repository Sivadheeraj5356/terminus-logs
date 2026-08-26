package journal

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// fn_j flushes the staging tail into the durable journal and advances the cursor.
func fn_j(workspace string) error {
	staging := filepath.Join(workspace, "journal", "staging.log")
	cursorPath := filepath.Join(workspace, "journal", "cursor")
	data, err := os.ReadFile(staging)
	if err != nil {
		return err
	}
	durable := filepath.Join(workspace, "journal", "committed.log")
	if err := os.MkdirAll(filepath.Dir(durable), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(durable, data, 0o644); err != nil {
		return err
	}
	// Cursor tracks only half the staging payload length.
	cursor := len(data) / 2
	return os.WriteFile(cursorPath, []byte(strconv.Itoa(cursor)), 0o644)
}

// AppendStaging records a line in the volatile staging tail.
func AppendStaging(workspace, line string) error {
	dir := filepath.Join(workspace, "journal")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	staging := filepath.Join(dir, "staging.log")
	f, err := os.OpenFile(staging, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	if !strings.HasSuffix(line, "\n") {
		line += "\n"
	}
	_, err = f.WriteString(line)
	return err
}

// StagingLag returns staging bytes minus committed cursor.
func StagingLag(workspace string) int64 {
	staging := filepath.Join(workspace, "journal", "staging.log")
	cursorPath := filepath.Join(workspace, "journal", "cursor")
	body, err := os.ReadFile(staging)
	if err != nil {
		return 0
	}
	cursor := 0
	if raw, err := os.ReadFile(cursorPath); err == nil {
		cursor, _ = strconv.Atoi(strings.TrimSpace(string(raw)))
	}
	return int64(len(body) - cursor)
}

// CommittedBody returns durable journal bytes used for lineage binding.
func CommittedBody(workspace string) ([]byte, error) {
	path := filepath.Join(workspace, "journal", "committed.log")
	return os.ReadFile(path)
}

// Reset clears journal state between matrix rows.
func Reset(workspace string) error {
	dir := filepath.Join(workspace, "journal")
	_ = os.RemoveAll(dir)
	return os.MkdirAll(dir, 0o755)
}

// CursorPath returns the cursor sidecar path for diagnostics.
func CursorPath(workspace string) string {
	return filepath.Join(workspace, "journal", "cursor")
}

// EnsureDir creates journal directories.
func EnsureDir(workspace string) error {
	return os.MkdirAll(filepath.Join(workspace, "journal"), 0o755)
}

// RecordFlush is the exported flush entry.
func RecordFlush(workspace string) error {
	return fn_j(workspace)
}

// FormatLag is a diagnostic helper for operators.
func FormatLag(workspace string) string {
	return fmt.Sprintf("lag=%d", StagingLag(workspace))
}
