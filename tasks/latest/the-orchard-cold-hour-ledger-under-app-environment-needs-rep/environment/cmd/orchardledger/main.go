package main

import (
	"flag"
	"fmt"
	"log"
	"os"

	"orchard/canopyledger/accum"
	"orchard/canopyledger/config"
	"orchard/canopyledger/emit"
	"orchard/canopyledger/parse"
	"orchard/canopyledger/replay"
	"orchard/canopyledger/util"
)

func main() {
	if len(os.Args) < 2 {
		util.Usage("usage: canopyledger [--profile <toml> --sensors <csv> --out <dir>] | [replay --manifest <toml> --out <dir> [--state <json>]]")
	}
	if os.Args[1] == "replay" {
		runReplay(os.Args[2:])
		return
	}
	runSimple(os.Args[1:])
}

func runSimple(args []string) {
	fs := flag.NewFlagSet("simple", flag.ExitOnError)
	profilePath := fs.String("profile", "", "orchard site toml")
	sensorsPath := fs.String("sensors", "", "sensor csv")
	outDir := fs.String("out", "", "output directory")
	if err := fs.Parse(args); err != nil {
		util.Usage("usage: canopyledger --profile <toml> --sensors <csv> --out <dir>")
	}
	if *profilePath == "" || *sensorsPath == "" || *outDir == "" {
		util.Usage("usage: canopyledger --profile <toml> --sensors <csv> --out <dir>")
	}
	site, err := config.LoadSettings(*profilePath)
	if err != nil {
		fail(err)
	}
	readings, err := parse.LoadReadings(*sensorsPath)
	if err != nil {
		fail(err)
	}
	rows := accum.Build(site, readings)
	if err := os.MkdirAll(*outDir, 0o755); err != nil {
		fail(err)
	}
	if err := emit.WriteLedger(*outDir+"/s7_ledger.jsonl", rows); err != nil {
		fail(err)
	}
}

func runReplay(args []string) {
	fs := flag.NewFlagSet("replay", flag.ExitOnError)
	manifestPath := fs.String("manifest", "", "replay manifest toml")
	outDir := fs.String("out", "", "output directory")
	statePath := fs.String("state", "", "replay state json path")
	if err := fs.Parse(args); err != nil {
		util.Usage("usage: canopyledger replay --manifest <toml> --out <dir> [--state <json>]")
	}
	if *manifestPath == "" || *outDir == "" {
		util.Usage("usage: canopyledger replay --manifest <toml> --out <dir> [--state <json>]")
	}
	st := *statePath
	if st == "" {
		st = *outDir + "/replay_state.json"
	}
	if err := os.MkdirAll(*outDir, 0o755); err != nil {
		fail(err)
	}
	if err := replay.Run(*manifestPath, *outDir, st); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}

func init() {
	log.SetFlags(0)
}
