package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"fxdesk/internal/io"
	"fxdesk/internal/model"
	footcacheint "fxdesk/internal/footcache"
	"fxdesk/internal/run"
)

const statePath = "/app/environment/var/work/state.json"

func main() {
	if err := execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func execute() error {
	caseID := flag.String("case", "", "case id")
	phase := flag.String("phase", "verify", "seal verify or append")
	outPath := flag.String("out", "", "output path")
	flag.Parse()
	if *caseID == "" || *phase == "" || *outPath == "" {
		return fmt.Errorf("usage: fxctl --case <id> --phase <seal|verify|append> --out <path>")
	}
	spec, err := io.LoadCase(*caseID)
	if err != nil {
		return err
	}
	state, err := loadState()
	if err != nil {
		return err
	}
	seq := run.BumpSeq(state, *caseID, *phase)
	store := footcacheint.ApplyWorkState(state)
	ctx := &model.Ctx{CaseID: *caseID, Phase: *phase, Seq: seq}
	doc, err := run.Drive(ctx, spec, store, state)
	if err != nil {
		return err
	}
	if err := writeRecord(*outPath, doc); err != nil {
		return err
	}
	footcacheint.SnapshotStore(store, state)
	return saveState(state)
}

func loadState() (*model.WorkState, error) {
	raw, err := os.ReadFile(statePath)
	if err != nil {
		if os.IsNotExist(err) {
			return &model.WorkState{}, nil
		}
		return nil, err
	}
	var st model.WorkState
	if err := json.Unmarshal(raw, &st); err != nil {
		return nil, err
	}
	return &st, nil
}

func saveState(st *model.WorkState) error {
	if err := os.MkdirAll(filepath.Dir(statePath), 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(st)
	if err != nil {
		return err
	}
	return os.WriteFile(statePath, raw, 0o644)
}

func writeRecord(path string, doc *model.SyncRecord) error {
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}
