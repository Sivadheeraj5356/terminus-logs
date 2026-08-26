package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/cinecont/desk/matchmesh"
	"github.com/cinecont/desk/spliceclock"
	"github.com/cinecont/desk/vaultseal"
)

type CaseFile struct {
	CaseID    string               `json:"case_id"`
	TempC     float64              `json:"temp_c"`
	RHPct     float64              `json:"rh_pct"`
	Threshold float64              `json:"threshold"`
	Reels     []spliceclock.ReelInput `json:"reels"`
	Splices   []spliceclock.Splice `json:"splices"`
}

func main() {
	if len(os.Args) < 2 || os.Args[1] != "run" {
		fmt.Fprintf(os.Stderr, "usage: cinecont run --case <file> --out <dir>\n")
		os.Exit(2)
	}
	casePath := ""
	outDir := "/app/output"
	for i := 2; i < len(os.Args); i++ {
		if os.Args[i] == "--case" && i+1 < len(os.Args) {
			casePath = os.Args[i+1]
			i++
		}
		if os.Args[i] == "--out" && i+1 < len(os.Args) {
			outDir = os.Args[i+1]
			i++
		}
	}
	if casePath == "" {
		fmt.Fprintf(os.Stderr, "invalid continuum case input: missing --case\n")
		os.Exit(1)
	}
	raw, err := os.ReadFile(casePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid continuum case input: %v\n", err)
		os.Exit(1)
	}
	var cf CaseFile
	if err := json.Unmarshal(raw, &cf); err != nil || cf.CaseID == "" || len(cf.Reels) == 0 {
		_ = os.Remove(filepath.Join(outDir, "continuum_report.json"))
		fmt.Fprintf(os.Stderr, "invalid continuum case input: malformed case payload\n")
		os.Exit(1)
	}
	thr := matchmesh.ThrOrDefault(cf.Threshold)
	denscorePath := "/app/bin/denscore"
	if v := os.Getenv("DENSCORE_BIN"); v != "" {
		denscorePath = v
	}

	prev, _ := vaultseal.LoadState(outDir)
	epoch := prev.Epoch + 1
	warmPath := spliceclock.DefaultWarmPath(outDir)
	cache := spliceclock.NewCache(epoch, warmPath)

	reelMap := make(map[string]spliceclock.ReelInput)
	for _, r := range cf.Reels {
		reelMap[r.ReelID] = r
	}
	densByReel := make(map[string]spliceclock.ReelDens)
	var allDens []spliceclock.ReelDens
	for _, r := range cf.Reels {
		d, err := cache.Lookup(r.ReelID, epoch, cf.TempC, cf.RHPct, r, denscorePath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "invalid continuum case input: denscore failure: %v\n", err)
			os.Exit(1)
		}
		densByReel[r.ReelID] = d
		allDens = append(allDens, d)
	}

	ordered := spliceclock.OrderSplices(cf.Splices)
	var spliceReports []vaultseal.SpliceReport
	allOK := true
	for _, sp := range ordered {
		a := densByReel[sp.ReelA]
		b := densByReel[sp.ReelB]
		gaps, ok := matchmesh.ScoreSplice(
			matchmesh.Channels{Cyan: a.End.Cyan, Magenta: a.End.Magenta, Yellow: a.End.Yellow, Silver: a.End.Silver},
			matchmesh.Channels{Cyan: a.Mid.Cyan, Magenta: a.Mid.Magenta, Yellow: a.Mid.Yellow, Silver: a.Mid.Silver},
			matchmesh.Channels{Cyan: b.Start.Cyan, Magenta: b.Start.Magenta, Yellow: b.Start.Yellow, Silver: b.Start.Silver},
			matchmesh.Channels{Cyan: b.Mid.Cyan, Magenta: b.Mid.Magenta, Yellow: b.Mid.Yellow, Silver: b.Mid.Silver},
			thr,
		)
		if !ok {
			allOK = false
		}
		spliceReports = append(spliceReports, vaultseal.SpliceReport{
			SpliceID: sp.SpliceID,
			Gaps:     gaps,
			OK:       ok,
		})
	}
	verdict := "pass"
	if !allOK {
		verdict = "fail"
	}
	report := vaultseal.Report{
		CaseID:           cf.CaseID,
		ContinuumVerdict: verdict,
		Splices:          spliceReports,
		DenscoreDigest:   vaultseal.DenscoreDigest(allDens),
	}
	ledger := vaultseal.LoadLedger(outDir)
	if err := cache.Persist(); err != nil {
		fmt.Fprintf(os.Stderr, "cache persist failed: %v\n", err)
		os.Exit(1)
	}
	if err := vaultseal.WriteArtifacts(outDir, report, epoch, cache.Digest(), thr, ledger); err != nil {
		fmt.Fprintf(os.Stderr, "artifact write failed: %v\n", err)
		os.Exit(1)
	}
	_ = filepath.Clean(outDir)
}
