package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/terminus/hopledger/checkpoint"
	"github.com/terminus/hopledger/digest"
	"github.com/terminus/hopledger/emit"
	"github.com/terminus/hopledger/ingest"
	"github.com/terminus/hopledger/ledger"
	"github.com/terminus/hopledger/policy"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	if os.Args[1] != "run" {
		fmt.Fprintln(os.Stderr, "unknown subcommand")
		os.Exit(2)
	}

	fs := flag.NewFlagSet("run", flag.ExitOnError)
	manifestPath := fs.String("manifest", "", "manifest json path")
	reportPath := fs.String("report", "", "report json path")
	digestPath := fs.String("digest", "", "digest text path")
	auditPath := fs.String("audit", "", "audit jsonl path")
	resumeTag := fs.String("resume-tag", "", "checkpoint tag to resume from")
	_ = fs.Parse(os.Args[2:])

	if *manifestPath == "" || *reportPath == "" || *digestPath == "" || *auditPath == "" {
		fmt.Fprintln(os.Stderr, "missing required flags")
		os.Exit(2)
	}

	if err := run(*manifestPath, *reportPath, *digestPath, *auditPath, *resumeTag); err != nil {
		fmt.Fprintln(os.Stderr, err)
		emit.CleanupOutputs(*reportPath, *digestPath, *auditPath)
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: hopledger run --manifest PATH --report PATH --digest PATH [--audit PATH] [--resume-tag TAG]")
}

func run(manifestPath, reportPath, digestPath, auditPath, resumeTag string) error {
	manifest, err := ingest.LoadManifest(manifestPath)
	if err != nil {
		return err
	}
	base := filepath.Dir(manifestPath)
	checkpointDir := manifest.Resolve(base, manifest.CheckpointDir)

	rawLines, err := ingest.LoadRawLines(manifest, base)
	if err != nil {
		return err
	}
	rawInputDigest := ingest.ComputeRawInputDigest(rawLines)

	records, err := ingest.BuildRecords(rawLines)
	if err != nil {
		return err
	}
	winners := ingest.SelectWinners(records)

	var initialPolicy *policy.Document
	policyDigest := ""
	if manifest.Policy != "" {
		policyPath := manifest.Resolve(base, manifest.Policy)
		doc, err := policy.Load(policyPath)
		if err != nil {
			return err
		}
		initialPolicy = &doc
		policyDigest, err = policy.DigestFile(policyPath)
		if err != nil {
			return err
		}
	}

	if resumeTag != "" {
		snap, err := checkpoint.Load(checkpointDir, resumeTag)
		if err != nil {
			return err
		}
		if err := ledger.ValidateResume(snap, rawInputDigest, records); err != nil {
			return err
		}
	}

	report, audit, err := ledger.Replay(records, winners, rawInputDigest, initialPolicy, policyDigest, checkpointDir)
	if err != nil {
		return err
	}

	if err := emit.WriteReport(reportPath, report); err != nil {
		return err
	}

	reportCanon, err := emit.ReportCanon(report)
	if err != nil {
		return err
	}
	auditMaps := emit.AuditMaps(audit)
	sum := digest.ComputeDigest(reportCanon, rawInputDigest, report.PolicyLineageDigest, auditMaps)
	if err := emit.WriteDigest(digestPath, sum); err != nil {
		return err
	}

	if auditPath != "" {
		if err := emit.WriteAudit(auditPath, audit); err != nil {
			return err
		}
	}
	return nil
}
