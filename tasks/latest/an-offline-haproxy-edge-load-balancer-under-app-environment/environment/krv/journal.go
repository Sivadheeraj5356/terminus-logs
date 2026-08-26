package krv

import (
	"encoding/json"
	"os"
	"path/filepath"

	"qxhub/fyn"
	"qxhub/pth"
)

// RecordCut journals an interrupted arm for a later recover pass.
func RecordCut(arm string, rows []fyn.LaneRow) error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	e := Entry{Arm: arm, Pending: len(rows)}
	if len(rows) > 0 && len(rows[0].Match) > 0 {
		e.Hint = rows[0].Match[0]
		hint := map[string]string{
			"kind":   rows[0].Kind,
			"match":  rows[0].Match[0],
			"target": rows[0].Target,
		}
		hb, err := json.MarshalIndent(hint, "", "  ")
		if err != nil {
			return err
		}
		if err := os.WriteFile(pth.LaneShadow(), append(hb, '\n'), 0o644); err != nil {
			return err
		}
	}
	raw, err := json.MarshalIndent(e, "", "  ")
	if err != nil {
		return err
	}
	name := filepath.Join(pth.JournalDir(), arm+".jnl")
	return os.WriteFile(name, append(raw, '\n'), 0o644)
}

// Replay consumes any pending cut journal ahead of a recover arm.
func Replay() error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	return nil
}

// HasPending reports whether any cut journal entries remain.
func HasPending() bool {
	entries, err := os.ReadDir(pth.JournalDir())
	if err != nil {
		return false
	}
	for _, e := range entries {
		if filepath.Ext(e.Name()) == ".jnl" {
			return true
		}
	}
	return false
}
