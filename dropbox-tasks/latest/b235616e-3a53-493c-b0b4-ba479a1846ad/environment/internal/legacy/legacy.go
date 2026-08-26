package legacy

import (
	"baylock/internal/pol"
)

type LegacyRow struct {
	Principal string `json:"principal"`
	Failures  int    `json:"failures"`
	Locked    bool   `json:"locked"`
}

type LegacyFile struct {
	GeneratedFrom string      `json:"generated_from"`
	Rows          []LegacyRow `json:"rows"`
}

// ApplyIfNeeded is unfinished.
func ApplyIfNeeded(migrated *bool, engine *pol.Engine) error {
	_ = engine
	*migrated = true
	return nil
}
