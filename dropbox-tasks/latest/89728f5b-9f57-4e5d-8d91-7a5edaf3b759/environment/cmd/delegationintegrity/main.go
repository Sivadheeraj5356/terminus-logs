package main

import (
	"encoding/json"
	"fmt"
	"os"

	"delegationintegrity/internal/elwjwire"
	"delegationintegrity/internal/inheritance_engine"
)

type reconcileCatalog struct {
	DelegationSlices []string `json:"delegation_slices"`
}

func main() {
	fixtureRoot := "/app/delegation_federation_slices"
	catalogPath := fixtureRoot + "/federation_slice_roll.json"
	outPath := "/app/build/delegation_integrity_snapshot.json"

	raw, err := os.ReadFile(catalogPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read catalog: %v\n", err)
		os.Exit(1)
	}
	var catalog reconcileCatalog
	if err := json.Unmarshal(raw, &catalog); err != nil {
		fmt.Fprintf(os.Stderr, "parse catalog: %v\n", err)
		os.Exit(1)
	}

	report := inheritance_engine.Report{DelegationSlices: make([]inheritance_engine.SliceOut, 0, len(catalog.DelegationSlices))}
	for _, id := range catalog.DelegationSlices {
		cfgPath := fixtureRoot + "/" + id + ".json"
		wormPath := fixtureRoot + "/" + id + "/inheritance_journal.elwj"
		sl, err := inheritance_engine.LoadDelegationSlice(cfgPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "load %s: %v\n", cfgPath, err)
			os.Exit(1)
		}
		events, wormStats, err := elwjwire.Decode(wormPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "decode %s: %v\n", wormPath, err)
			os.Exit(1)
		}
		sl.Events = events
		wormOut := inheritance_engine.InheritanceJournalOut{
			FormatVersion:   wormStats.FormatVersion,
			RecordsTotal:    wormStats.RecordsTotal,
			RecordsValid:    wormStats.RecordsValid,
			RecordsRejected: wormStats.RecordsRejected,
			DupSeqRejects:   wormStats.DupSeqRejects,
			TruncatedTail:   wormStats.TruncatedTail,
			PayloadBytes:    wormStats.PayloadBytes,
		}
		report.DelegationSlices = append(report.DelegationSlices, inheritance_engine.Reconcile(sl, wormOut))
	}

	if err := os.MkdirAll("/app/build", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	enc, err := json.Marshal(report)
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
		os.Exit(1)
	}
	out := append(enc, '\n')
	if err := os.WriteFile(outPath, out, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
