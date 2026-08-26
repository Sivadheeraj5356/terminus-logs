package main

import (
	"fmt"
	"os"

	"ot7/internal/export"
)

func main() {
	rep, err := export.LoadReport()
	if err != nil {
		fmt.Println("drift")
		os.Exit(1)
	}
	var digests []string
	for _, p := range rep.Profiles {
		if p.Accepted {
			digests = append(digests, p.PlanDigestHex)
		}
	}
	expect := export.ReportDigest(rep.Generation, rep.PolicyEpoch, digests)
	if expect == rep.ReportDigestHex {
		fmt.Println("aligned")
		return
	}
	fmt.Println("drift")
	os.Exit(1)
}
