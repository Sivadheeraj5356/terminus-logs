package main

import (
	"fmt"
	"os"
	"path/filepath"

	"desk/desk"
)

func main() {
	root := os.Getenv("DESK_ROOT")
	if root == "" {
		root = "/app"
	}
	index := filepath.Join(root, "shared", "pack_index.json")
	curves := filepath.Join(root, "curves")
	outDir := filepath.Join(root, "output")
	workDir := filepath.Join(root, "work")
	_ = os.MkdirAll(workDir, 0o755)
	_ = os.MkdirAll(outDir, 0o755)

	order, err := desk.LoadOrder(index)
	if err != nil {
		panic(err)
	}

	rows := make([]desk.Row, 0, len(order))
	allOk := true
	for _, name := range order {
		spec, err := desk.LoadSpec(filepath.Join(curves, name+".json"))
		if err != nil {
			panic(err)
		}
		fresh, rf := desk.FreshLane(spec, workDir)
		resumed, rr := desk.ResumeLane(spec, workDir)
		second, _ := desk.ResumeLane(spec, workDir)
		parity := fresh == resumed
		dual := resumed == second
		if !parity || !dual {
			allOk = false
		}
		rows = append(rows, desk.Row{
			Pack:            name,
			FreshDepth:      fresh,
			ResumedDepth:    resumed,
			SecondDepth:     second,
			ResidualFresh:   rf,
			ResidualResumed: rr,
			DepthParityOk:   parity,
			DualResumeOk:    dual,
		})
	}
	if err := desk.EmitReport(outDir, rows, allOk); err != nil {
		panic(err)
	}
	fmt.Printf("wrote %s (%d packs)\n", filepath.Join(outDir, "depth_report.json"), len(rows))
}
