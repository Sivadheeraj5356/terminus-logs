package main

// Formula home (do not hand-write JSON):
//   span_band = 16
//   facet_hex = lowercase 16-hex encoding of the uint64 facet for a target
//   ledger_digest = sha256 hex of the comma-joined sorted facet_hex values
//                   for primary targets a1,b2,g3 only (echoes excluded)
//   lag = 0 when a primary and its _echo twin share the same facet_hex
//   feat_rc/dep_rc/ord_rc = 1 on coherent terminal rows; sync_label = settled

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"ucg.local/workspace/engine"
)

func main() {
	scenario := flag.String("scenario", "", "scenario name")
	arm := flag.String("arm", "arm0", "arm id")
	phase := flag.String("phase", "cold", "cold|warm|replay")
	status := flag.Bool("status", false, "print status probe after pipeline")
	statusOnly := flag.Bool("status-only", false, "print status probe without rerunning pipeline")
	flag.Parse()
	if *scenario != "unit-conversion-graph" {
		fmt.Fprintf(os.Stderr, "unsupported scenario %q\n", *scenario)
		os.Exit(2)
	}
	root := "/app/environment"
	out := "/app/output"
	if !*statusOnly {
		if err := engine.RunPipeline(engine.RunOpts{Arm: *arm, Phase: *phase, Root: root, Out: out}); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if *status || *statusOnly {
		ok, n, err := engine.DurableAgrees(out, filepath.Join(out, "conversion_ledger.json"))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		var buf bytes.Buffer
		_ = engine.EmitStatusView(&buf, engine.ProbeSnap{DurableMatch: ok, Rows: n})
		os.Stdout.Write(buf.Bytes())
	}
}
