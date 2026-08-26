package main

import (
	"flag"
	"fmt"
	"os"

	"burstverify/driver"
	"burstverify/journalspan"
)

func main() {
	fixturesDir := flag.String("fixtures-dir", "", "directory containing JSON fixtures")
	outPath := flag.String("out", "", "path for run_records.json")
	tracePath := flag.String("trace-out", "", "path for export_trace.jsonl")
	journalPath := flag.String("journal-out", "", "path for span_journal.jsonl")
	completionManifestPath := flag.String("manifest-out", "", "path for completion_manifest.jsonl")
	auditPath := flag.String("audit-out", "", "path for run_audit.jsonl")
	ledgerStatePath := flag.String("ledger-state", "", "path for run_ledger.state")
	flag.Parse()
	if *fixturesDir == "" || *outPath == "" {
		fmt.Fprintln(os.Stderr, "usage: verify-journal-runs --fixtures-dir DIR --out PATH [--trace-out PATH] [--journal-out PATH] [--manifest-out PATH] [--audit-out PATH] [--ledger-state PATH]")
		os.Exit(2)
	}
	prior, err := journalspan.LoadRunLedger(*ledgerStatePath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if *auditPath != "" {
		if err := journalspan.ResetAudit(*auditPath); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	runs, err := driver.DriveAll(*fixturesDir, *tracePath, *journalPath, *completionManifestPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := journalspan.WriteReport(*outPath, runs); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := journalspan.AuditArtifacts(*outPath, *journalPath, *completionManifestPath, *auditPath); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := journalspan.FinalizeRunLedger(*ledgerStatePath, *auditPath, prior); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
