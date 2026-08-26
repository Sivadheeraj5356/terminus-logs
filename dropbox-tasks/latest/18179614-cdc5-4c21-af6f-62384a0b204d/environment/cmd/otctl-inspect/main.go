package main

import (
	"fmt"
	"os"

	"ot7/internal/export"
)

func main() {
	if len(os.Args) < 2 {
		os.Exit(2)
	}
	rep, err := export.LoadReport()
	if err != nil {
		os.Exit(2)
	}
	label := os.Args[1]
	for _, p := range rep.Profiles {
		if p.Label == label {
			fmt.Println(p.InstanceID)
			return
		}
	}
	os.Exit(2)
}
