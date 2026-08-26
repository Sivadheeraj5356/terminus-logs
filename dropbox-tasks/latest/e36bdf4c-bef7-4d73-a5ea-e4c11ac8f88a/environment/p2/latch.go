package p2

import (
	"os"
)

const latchPath = "/app/output/.ov_persist/pref_latch"

func LatchClear() error {
	if err := os.MkdirAll("/app/output/.ov_persist", 0o755); err != nil {
		return err
	}
	return os.WriteFile(latchPath, []byte("0"), 0o644)
}

func LatchSet(val string) error {
	if err := os.MkdirAll("/app/output/.ov_persist", 0o755); err != nil {
		return err
	}
	return os.WriteFile(latchPath, []byte(val), 0o644)
}

func LatchActive() bool {
	b, err := os.ReadFile(latchPath)
	if err != nil {
		return false
	}
	return len(b) > 0
}
