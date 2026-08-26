package zeb

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"qxhub/pth"
)

// Load reads the durable session registry.
func Load() (Session, error) {
	var s Session
	raw, err := os.ReadFile(pth.SessionPath())
	if err != nil {
		if os.IsNotExist(err) {
			return Session{ActiveGen: 1, Floor: 0, Anchor: SealAnchor(1, 0, 0), Epoch: 0}, nil
		}
		return s, err
	}
	err = json.Unmarshal(raw, &s)
	return s, err
}

// Save writes the durable session registry.
func Save(s Session) error {
	if err := os.MkdirAll(filepath.Dir(pth.SessionPath()), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(pth.SessionPath(), append(raw, '\n'), 0o644)
}

// SealAnchor is the durable seal documented in docs/inv_fields.md:
// lowercase hex of active_gen*13 + floor*5 + epoch.
func SealAnchor(gen, floor, epoch int) string {
	return fmt.Sprintf("%x", gen*13+floor*5+epoch)
}
