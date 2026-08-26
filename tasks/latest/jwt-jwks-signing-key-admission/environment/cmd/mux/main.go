package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"jwksbound.local/mux/cli"
	"jwksbound.local/mux/tools"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: mux <audit|pulse> [--profile <name>]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "audit":
		fs := flag.NewFlagSet("audit", flag.ExitOnError)
		profile := fs.String("profile", "", "profile name")
		_ = fs.Parse(os.Args[2:])
		if *profile == "" {
			fmt.Fprintln(os.Stderr, "profile required")
			os.Exit(2)
		}
		cli.RunAudit(*profile)
	case "pulse":
		profile := "onyx"
		if len(os.Args) > 2 {
			profile = os.Args[2]
		}
		out := tools.LaneProbe(profile)
		data, _ := json.Marshal(out)
		fmt.Println(string(data))
	default:
		fmt.Fprintln(os.Stderr, "unknown command")
		os.Exit(2)
	}
}
