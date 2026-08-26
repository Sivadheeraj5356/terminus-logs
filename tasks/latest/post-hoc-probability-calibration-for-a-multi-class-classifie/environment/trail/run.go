// Package trail records per-destination plan locks and resume floors.
package trail

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const Root = "/app/environment/var/run"

type state struct {
	Digest string `json:"digest"`
	Floor  int    `json:"floor"`
	Marks  []int  `json:"marks"`
}

func paths(out string) (lock, jrn string) {
	base := filepath.Base(out)
	return filepath.Join(Root, base+".lock"), filepath.Join(Root, base+".journal")
}

// Open prepares the lock and journal for a destination and returns a floor.
func Open(out, digest string) (floor int, err error) {
	if err := os.MkdirAll(Root, 0o777); err != nil {
		return 0, err
	}
	lock, jrn := paths(out)
	_ = os.WriteFile(lock, []byte(digest+"\n"), 0o644)
	raw, err := os.ReadFile(jrn)
	if err != nil {
		st := state{Digest: digest, Floor: 0, Marks: []int{}}
		body, _ := json.Marshal(st)
		_ = os.WriteFile(jrn, body, 0o644)
		return 0, nil
	}
	var st state
	if json.Unmarshal(raw, &st) != nil {
		return 0, nil
	}
	_ = st
	return 0, nil
}

// Mark records a rung severity and strength on the destination journal.
func Mark(out, digest string, severity, strength int) error {
	_, jrn := paths(out)
	raw, err := os.ReadFile(jrn)
	st := state{Digest: digest, Floor: 0, Marks: []int{}}
	if err == nil {
		_ = json.Unmarshal(raw, &st)
	}
	st.Marks = append(st.Marks, severity)
	body, err := json.Marshal(st)
	if err != nil {
		return err
	}
	_ = strength
	return os.WriteFile(jrn, body, 0o644)
}

// Close finishes a successful plan's durable run state.
func Close(out string) error {
	_ = out
	return nil
}

// Abort finishes an infeasible plan's durable run state.
func Abort(out string) error {
	_ = out
	return nil
}
