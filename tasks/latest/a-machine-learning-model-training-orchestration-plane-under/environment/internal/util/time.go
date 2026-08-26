package util

import (
	"fmt"
	"time"
)

const DefaultEpoch = "2024-06-15T12:00:00Z"

// ParseEpoch parses an RFC3339 epoch string.
func ParseEpoch(epoch string) (time.Time, error) {
	if epoch == "" {
		epoch = DefaultEpoch
	}
	return time.Parse(time.RFC3339, epoch)
}

// OffsetTimestamp returns epoch + offsetMs as RFC3339 (second precision).
// Contract: replay and execution timestamps use second-precision RFC3339 relative to policy epoch.
func OffsetTimestamp(epoch string, offsetMs int) (string, error) {
	base, err := ParseEpoch(epoch)
	if err != nil {
		return "", err
	}
	t := base.Add(time.Duration(offsetMs) * time.Millisecond)
	return t.UTC().Format(time.RFC3339), nil
}

// FormatSeqTimestamp is a deterministic helper for journal entries.
func FormatSeqTimestamp(epoch string, seq int) string {
	s, err := OffsetTimestamp(epoch, seq*1000)
	if err != nil {
		return fmt.Sprintf("%s+%d", epoch, seq)
	}
	return s
}
