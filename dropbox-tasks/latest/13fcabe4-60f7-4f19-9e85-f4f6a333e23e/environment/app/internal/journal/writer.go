package journal

import (
	"os"

	"zonepub/internal/fsutil"
)

func Append(path string, rec Record) error {
	line, err := rec.Line()
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	if _, err := f.Write(line); err != nil {
		return err
	}
	if err := f.Sync(); err != nil {
		return err
	}
	return fsutil.SyncDir(os.Getenv("WORKSPACE_DIR"))
}
