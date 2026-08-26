package main

import (
	"fmt"
	"os"

	"contactdebugger/engine/export"
	"contactdebugger/engine/orchestrator"
)

const outPath = "/app/results/contact_stability_report.json"

func main() {
	rpt, err := orchestrator.Run()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := export.Write(outPath, rpt); err != nil {
		fmt.Fprintln(os.Stderr, "write report:", err)
		os.Exit(1)
	}
}
