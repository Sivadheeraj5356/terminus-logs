package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"

	"g7.example/attest/journal"
	"g7.example/attest/layer_core"
	"g7.example/attest/m5"
	"g7.example/attest/m7"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: g7bridge <cmd> [args...]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "replay":
		if len(os.Args) != 4 {
			fmt.Fprintln(os.Stderr, "usage: g7bridge replay <journal> <config>")
			os.Exit(2)
		}
		pkg, err := journal.SettlePackage(os.Args[2], os.Args[3])
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		encoder := json.NewEncoder(os.Stdout)
		encoder.SetEscapeHTML(false)
		if err := encoder.Encode(pkg); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "fold":
		if len(os.Args) != 5 {
			os.Exit(2)
		}
		step, _ := strconv.Atoi(os.Args[2])
		fam, _ := strconv.ParseUint(os.Args[3], 10, 32)
		prev, _ := strconv.ParseUint(os.Args[4], 10, 32)
		fmt.Println(m5.FoldLinkA(step, uint32(fam), uint32(prev)))
	case "hex16":
		if len(os.Args) != 3 {
			os.Exit(2)
		}
		v, _ := strconv.ParseUint(os.Args[2], 10, 64)
		fmt.Println(layercore.Hex16(v))
	case "necklag":
		if len(os.Args) != 5 {
			os.Exit(2)
		}
		meas, _ := strconv.ParseFloat(os.Args[2], 64)
		up, _ := strconv.ParseFloat(os.Args[3], 64)
		stress := os.Args[4] == "1"
		fmt.Println(m7.NeckLag(meas, up, stress))
	case "emit_slow":
		if len(os.Args) != 4 {
			os.Exit(2)
		}
		step, _ := strconv.Atoi(os.Args[2])
		stamp, _ := strconv.ParseUint(os.Args[3], 10, 64)
		fmt.Println(layercore.FormatLaneLine(step, stamp))
	case "emit_fast":
		if len(os.Args) != 4 {
			os.Exit(2)
		}
		step, _ := strconv.Atoi(os.Args[2])
		stamp, _ := strconv.ParseUint(os.Args[3], 10, 64)
		fmt.Println(layercore.CatalogEmit(step, stamp))
	case "step_mux":
		if len(os.Args) != 3 {
			os.Exit(2)
		}
		gateFirst := os.Args[2] == "true"
		var touched bool
		mask := m7.StepMux(gateFirst, func() { touched = true }, func() { _ = touched })
		fmt.Println(mask)
	case "merge_hold":
		if len(os.Args) != 20 {
			os.Exit(2)
		}
		lastA, _ := strconv.ParseUint(os.Args[2], 10, 64)
		lastB, _ := strconv.ParseUint(os.Args[3], 10, 64)
		tagA, _ := strconv.ParseUint(os.Args[4], 10, 64)
		tagB, _ := strconv.ParseUint(os.Args[5], 10, 64)
		neckTm, _ := strconv.ParseFloat(os.Args[6], 64)
		uplinkTm, _ := strconv.ParseFloat(os.Args[7], 64)
		var incoming [3][4]float64
		idx := 8
		for r := 0; r < 3; r++ {
			for c := 0; c < 4; c++ {
				incoming[r][c], _ = strconv.ParseFloat(os.Args[idx], 64)
				idx++
			}
		}
		state := &m7.PackState{LastA: lastA, LastB: lastB, NeckTm: neckTm, UplinkTm: uplinkTm}
		inc := &m7.PackState{LastA: tagA, LastB: tagB, Storage: incoming, NeckTm: neckTm, UplinkTm: uplinkTm}
		out := m7.MergeHoldB(state, inc, tagB)
		state.Storage = out
		fmt.Printf("%d,%d,%g,%g", state.LastA, state.LastB, state.NeckTm, state.UplinkTm)
		for r := 0; r < 3; r++ {
			for c := 0; c < 4; c++ {
				fmt.Printf(",%g", state.Storage[r][c])
			}
		}
		fmt.Println()
	default:
		os.Exit(2)
	}
}
