package main

import (
	"fmt"
	"os"

	"ot7/internal/export"
	"ot7/internal/memstore"
	"ot7/internal/runbook"
)

func main() {
	if len(os.Args) < 2 {
		os.Exit(2)
	}
	rep, err := export.LoadReport()
	if err != nil {
		os.Exit(2)
	}
	if os.Args[1] == "wasserstein" {
		if len(os.Args) < 3 {
			os.Exit(2)
		}
		label := os.Args[2]
		for _, p := range rep.Profiles {
			if p.Label == label && p.Accepted {
				fmt.Printf("%.17g\n", p.Wasserstein)
				return
			}
		}
		os.Exit(2)
	}
	label := os.Args[1]
	for _, p := range rep.Profiles {
		if p.Label == label && p.Accepted {
			fmt.Println(p.PlanDigestHex)
			_ = memstore.Load()
			_ = runbook.Load()
			return
		}
	}
	os.Exit(2)
}
