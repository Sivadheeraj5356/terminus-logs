package main

import (
	"fmt"
	"os"
	"strconv"

	"example.com/claimdocketaudit/internal/report"
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "audit" {
		fmt.Fprintf(os.Stderr, "usage: %s audit --docket-dir <DIR> --epoch <N> --json-out <PATH>\n", os.Args[0])
		os.Exit(1)
	}

	var docketDir, jsonOut string
	var epoch uint32
	haveEpoch := false

	for i := 2; i < len(os.Args); i++ {
		switch os.Args[i] {
		case "--docket-dir":
			i++
			if i >= len(os.Args) {
				usage()
				os.Exit(1)
			}
			docketDir = os.Args[i]
		case "--epoch":
			i++
			if i >= len(os.Args) {
				usage()
				os.Exit(1)
			}
			v, err := strconv.ParseUint(os.Args[i], 10, 32)
			if err != nil {
				usage()
				os.Exit(1)
			}
			epoch = uint32(v)
			haveEpoch = true
		case "--json-out":
			i++
			if i >= len(os.Args) {
				usage()
				os.Exit(1)
			}
			jsonOut = os.Args[i]
		default:
			usage()
			os.Exit(1)
		}
	}

	if docketDir == "" || jsonOut == "" || !haveEpoch {
		usage()
		os.Exit(1)
	}

	if err := report.EmitReport(docketDir, epoch, jsonOut); err != nil {
		fmt.Fprintf(os.Stderr, "audit failed: %v\n", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, "usage: %s audit --docket-dir <DIR> --epoch <N> --json-out <PATH>\n", os.Args[0])
}
