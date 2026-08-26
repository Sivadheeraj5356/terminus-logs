package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type output struct {
	EventFindings    []any    `json:"event_findings"`
	Decisions        []any    `json:"decisions"`
	FinalSessions    []any    `json:"final_sessions"`
	ConsumedSessions []string `json:"consumed_sessions"`
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: breakglass-ledger input.json output.json")
		os.Exit(2)
	}
	if _, err := os.ReadFile(os.Args[1]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.MkdirAll(filepath.Dir(os.Args[2]), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data, err := json.MarshalIndent(output{
		EventFindings:    []any{},
		Decisions:        []any{},
		FinalSessions:    []any{},
		ConsumedSessions: []string{},
	}, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data = append(data, '\n')
	if err := os.WriteFile(os.Args[2], data, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
