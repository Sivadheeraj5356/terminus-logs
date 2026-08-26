package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"imlab/internal/knot"
	"imlab/internal/model"
	"imlab/internal/weave"
)

func main() {
	authDir := flag.String("authority", "data/authority", "authority directory")
	workloadPath := flag.String("workload", "data/workload.json", "workload")
	programPath := flag.String("program", "output/program.json", "lowered program")
	jobsPath := flag.String("jobs", "output/jobs.txt", "flat jobs")
	flag.Parse()

	var pin model.AuthorityPin
	if err := model.ReadJSON(filepath.Join(*authDir, "pin.json"), &pin); err != nil {
		die(err)
	}
	var idx model.AuthorityIndex
	if err := model.ReadJSON(filepath.Join(*authDir, "index.json"), &idx); err != nil {
		die(err)
	}
	var stamp model.AuthorityStamp
	if err := model.ReadJSON(filepath.Join(*authDir, "stamp.json"), &stamp); err != nil {
		die(err)
	}
	policyPath, err := knot.ResolvePolicy(*authDir, pin, idx, stamp)
	if err != nil {
		die(err)
	}
	p, raw, err := model.LoadPolicy(policyPath)
	if err != nil {
		die(err)
	}
	w, err := model.LoadWorkload(*workloadPath)
	if err != nil {
		die(err)
	}
	prog := weave.Lower(p, raw)
	if err := model.WriteJSON(*programPath, prog); err != nil {
		die(err)
	}
	if err := model.EmitJobs(w, *jobsPath); err != nil {
		die(err)
	}
}

func die(err error) {
	fmt.Fprintln(os.Stderr, "loader:", err)
	os.Exit(1)
}
