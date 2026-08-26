package main

import (
	"flag"
	"fmt"
	"os"

	"missiondesk/lib/driver"
	"missiondesk/lib/intake"
	"missiondesk/lib/cstore"
	"missiondesk/lib/render"
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "review" {
		fmt.Fprintln(os.Stderr, "usage: boardctl review --record DIR --policy FILE --out DIR --state FILE [--reset-state]")
		os.Exit(2)
	}
	fs := flag.NewFlagSet("review", flag.ExitOnError)
	recordDir := fs.String("record", "", "record directory")
	policyPath := fs.String("policy", "", "policy JSON")
	outDir := fs.String("out", "/app/output", "output directory")
	statePath := fs.String("state", "/app/var/board_state.json", "state file")
	reset := fs.Bool("reset-state", false, "start with empty review state")
	_ = fs.Parse(os.Args[2:])
	if *recordDir == "" || *policyPath == "" || *outDir == "" || *statePath == "" {
		fmt.Fprintln(os.Stderr, "record, policy, out, and state are required")
		os.Exit(2)
	}
	rec, err := intake.LoadRecord(*recordDir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	pol, err := intake.LoadPolicy(*policyPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	sf, err := cstore.LoadState(*statePath, *reset)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	assess, err := driver.Assess(rec, pol, sf)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := render.Publish(*outDir, assess, sf); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := cstore.SaveState(*statePath, sf); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("case=%s decision=%s resilience_index=%d\n", assess.CaseID, assess.Decision, assess.ResilienceIndex)
}
