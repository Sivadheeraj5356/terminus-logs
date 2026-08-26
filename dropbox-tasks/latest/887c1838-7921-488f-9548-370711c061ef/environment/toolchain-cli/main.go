package main

import (
	"fmt"
	"os"

	"artifactequiv/pipeline-runner"
	"artifactequiv/report-writer"
)

const outPath = "/app/output/equivalence_report.json"

func main() {
	rpt, err := runner.Run()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := writer.Write(outPath, rpt); err != nil {
		fmt.Fprintln(os.Stderr, "write report:", err)
		os.Exit(1)
	}
}
