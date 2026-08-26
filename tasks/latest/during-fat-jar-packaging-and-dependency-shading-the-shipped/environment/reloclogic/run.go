package reloclogic

import (
	"fmt"
	"os"
)

const (
	defaultBatchDir  = "/app/reloc-batches"
	defaultPolicyPath = "/app/reloc-canon/rules.yaml"
	outPath          = "/app/artifacts/relocation_consistency_report.json"
)

// Run loads batches and policy, evaluates each batch, and returns the report.
func Run() (Report, error) {
	dir := defaultBatchDir
	if v := os.Getenv("RELOC_BATCH_DIR"); v != "" {
		dir = v
	}
	policyPath := defaultPolicyPath
	if v := os.Getenv("RELOC_POLICY_PATH"); v != "" {
		policyPath = v
	}
	pol, err := LoadPolicy(policyPath)
	if err != nil {
		return Report{}, err
	}
	batches, err := LoadBatches(dir)
	if err != nil {
		return Report{}, err
	}
	rows := make([]BatchResult, 0, len(batches))
	var sum Summary
	sum.BatchesAnalyzed = len(batches)
	for _, bf := range batches {
		row := EvaluateBatch(bf, pol)
		rows = append(rows, row)
		if row.RelocationOK {
			sum.CleanBatches++
		} else {
			sum.FailedBatches++
		}
		sum.TotalFindings += len(row.Findings)
		sum.ReplayRuns += row.Replay.SchedulesRun
		sum.ReplayPassed += row.Replay.SchedulesPassed
	}
	if sum.CleanBatches+sum.FailedBatches != sum.BatchesAnalyzed {
		return Report{}, fmt.Errorf("summary reconciliation failed")
	}
	return Report{Summary: sum, Batches: rows}, nil
}

// WriteDefault writes the report to the standard artifact path.
func WriteDefault(rpt Report) error {
	return WriteReport(outPath, rpt)
}
