package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"vivostep.local/sim/observemit"
	"vivostep.local/sim/simdrive"
	"vivostep.local/sim/pkg/api"
)

const sessionPath = "/app/data/vivostep_session.json"

type sessionState struct {
	Cycles     []api.CycleRecord    `json:"cycles"`
	Surfaces   []api.SurfaceMeasure `json:"surfaces"`
	ProbeReady uint64               `json:"probe_ready"`
	Reopened   bool                 `json:"reopened"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: vivostep <run|examine|emit|reopen> ...")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "run":
		runCmd(os.Args[2:])
	case "examine":
		examineCmd(os.Args[2:])
	case "emit":
		emitCmd(os.Args[2:])
	case "reopen":
		reopenCmd()
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
		os.Exit(2)
	}
}

func runCmd(args []string) {
	fs := flag.NewFlagSet("run", flag.ExitOnError)
	scenario := fs.String("scenario", "", "scenario name")
	cold := fs.Bool("cold", false, "cold boot path")
	_ = fs.Parse(args)
	if *scenario == "" {
		fmt.Fprintln(os.Stderr, "scenario required")
		os.Exit(2)
	}
	seed := 1
	if v := os.Getenv("VIVO_SCHED_SEED"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			seed = n
		}
	}
	sess, _ := loadSession()
	eng, err := simdrive.NewEngine("/app", seed)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if sess.Reopened {
		if err := eng.Reopen(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if *cold {
		if err := eng.RunScenario(*scenario, true); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	} else {
		if err := eng.RunScenario(*scenario, false); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	sess.Cycles = append(sess.Cycles, eng.Cycles()...)
	sess.Surfaces = eng.ExamineDual()
	sess.ProbeReady = eng.ProbeReadyCount()
	if err := saveSession(sess); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func reopenCmd() {
	sess, err := loadSession()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	sess.Reopened = true
	if err := saveSession(sess); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func examineCmd(args []string) {
	fs := flag.NewFlagSet("examine", flag.ExitOnError)
	surface := fs.String("surface", "", "surface selector")
	_ = fs.Parse(args)
	if *surface != "dual" {
		fmt.Fprintln(os.Stderr, "only dual surface supported")
		os.Exit(2)
	}
	sess, err := loadSession()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	out := struct {
		Surfaces []api.SurfaceMeasure `json:"surfaces"`
	}{Surfaces: sess.Surfaces}
	b, _ := json.MarshalIndent(out, "", "  ")
	fmt.Println(string(b))
}

func emitCmd(args []string) {
	fs := flag.NewFlagSet("emit", flag.ExitOnError)
	outPath := fs.String("o", "", "output path")
	_ = fs.Parse(args)
	if *outPath == "" {
		fmt.Fprintln(os.Stderr, "output path required")
		os.Exit(2)
	}
	sess, err := loadSession()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := observemit.WriteReport(*outPath, observemit.ReportInput{
		Cycles:   sess.Cycles,
		Surfaces: sess.Surfaces,
	}); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func loadSession() (sessionState, error) {
	b, err := os.ReadFile(sessionPath)
	if err != nil {
		if os.IsNotExist(err) {
			return sessionState{}, nil
		}
		return sessionState{}, err
	}
	var s sessionState
	if err := json.Unmarshal(b, &s); err != nil {
		return sessionState{}, err
	}
	return s, nil
}

func saveSession(s sessionState) error {
	if err := os.MkdirAll(filepath.Dir(sessionPath), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(sessionPath, b, 0o644)
}
