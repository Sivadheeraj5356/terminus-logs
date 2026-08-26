package main

import (
	"flag"
	"fmt"
	"os"

	"imlab/internal/band"
	"imlab/internal/fusion"
	"imlab/internal/model"
	"imlab/internal/weave"
)

func main() {
	programPath := flag.String("program", "output/program.json", "lowered program")
	tracesPath := flag.String("traces", "output/read_traces.json", "recorded traces")
	logPath := flag.String("log", "output/measure_log.json", "digest log")
	manifestPath := flag.String("manifest", "data/manifest.json", "manifest")
	out := flag.String("out", "output/integrity_report.json", "report output")
	flag.Parse()

	var prog model.Program
	if err := model.ReadJSON(*programPath, &prog); err != nil {
		die(err)
	}
	var tr model.Traces
	if err := model.ReadJSON(*tracesPath, &tr); err != nil {
		die(err)
	}
	var ml model.MeasureLog
	if err := model.ReadJSON(*logPath, &ml); err != nil {
		die(err)
	}
	manifest, err := model.LoadManifest(*manifestPath)
	if err != nil {
		die(err)
	}

	logged := map[string]bool{}
	for _, row := range ml.Rows {
		logged[row.Path] = true
	}

	rep := model.Report{Schema: "integrity/v1", SetID: tr.SetID, Aligned: true}
	for _, tj := range tr.Jobs {
		rj := model.ReportJob{Name: tj.Name}
		for _, ev := range tj.Events {
			folded := weave.SoftPath(ev.Path)
			tier := band.Prefer(prog.Clauses, folded, weave.Holds)
			verbs := band.BitsAt(prog.Clauses, tier, folded, weave.Holds)
			_ = ev.Verbs
			ent := manifest[folded]
			outcome := fusion.Blend(verbs, ent.DigestHex, ent.HmacHex, ent.SigHex)
			wantLog := weave.WantsLog(verbs)
			wantCheck := weave.WantsCheck(verbs)
			obs := fusion.Outcome{Logged: logged[ev.Path], Check: outcome.Check}
			evRep := model.ReportEvent{
				Path:    ev.Path,
				Logged:  logged[ev.Path],
				Check:   outcome.Check,
				Verdict: fusion.Verdict(obs, wantLog, wantCheck),
			}
			if wantLog != logged[ev.Path] {
				rep.Aligned = false
			}
			rj.Events = append(rj.Events, evRep)
		}
		rep.Jobs = append(rep.Jobs, rj)
	}

	if err := model.WriteJSON(*out, rep); err != nil {
		die(err)
	}
}

func die(err error) {
	fmt.Fprintln(os.Stderr, "reconcile:", err)
	os.Exit(1)
}
