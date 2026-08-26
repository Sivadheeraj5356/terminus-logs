package ledger

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// Event is one probe observation appended during a session.
type Event struct {
	Profile string `json:"profile"`
	Step    int    `json:"step"`
	Tier    int    `json:"tier"`
	Epoch   int    `json:"epoch"`
	Owner   string `json:"owner"`
}

// File is the durable promotion ledger under /app/state.
type File struct {
	Events []Event `json:"events"`
}

func path(root string) string {
	return filepath.Join(root, "..", "state", "promo_ledger.json")
}

func Load(root string) (File, error) {
	raw, err := os.ReadFile(path(root))
	if err != nil {
		return File{}, nil
	}
	var f File
	if err := json.Unmarshal(raw, &f); err != nil {
		return File{}, err
	}
	return f, nil
}

func Save(root string, f File) error {
	p := path(root)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(f)
	if err != nil {
		return err
	}
	return os.WriteFile(p, raw, 0o644)
}

func Append(root string, ev Event) error {
	f, err := Load(root)
	if err != nil {
		return err
	}
	f.Events = append(f.Events, ev)
	return Save(root, f)
}

// Tip returns the last recorded event projection fields, or zeros when empty.
func Tip(f File) (tier, epoch int, owner string) {
	if len(f.Events) == 0 {
		return 0, 0, ""
	}
	last := f.Events[len(f.Events)-1]
	return last.Tier, last.Epoch, last.Owner
}
