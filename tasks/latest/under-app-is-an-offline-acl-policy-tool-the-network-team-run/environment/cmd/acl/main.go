// Command acl runs network flows against an ordered ACL ruleset. It has two
// subcommands, both printing JSON to stdout:
//
//	acl evaluate --rules <path> --flows <path>   per-flow allow/deny decisions
//	acl lint --rules <path> [--flows <path>]     rule warnings and dead-rule findings
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"example.com/acl/internal/cidr"
	"example.com/acl/internal/eval"
	"example.com/acl/internal/report"
	"example.com/acl/internal/ruleset"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: acl <evaluate|lint> --rules <path> [--flows <path>]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "evaluate":
		if err := runEvaluate(os.Args[2:]); err != nil {
			fmt.Fprintln(os.Stderr, "acl:", err)
			os.Exit(1)
		}
	case "lint":
		if err := runLint(os.Args[2:]); err != nil {
			fmt.Fprintln(os.Stderr, "acl:", err)
			os.Exit(1)
		}
	default:
		fmt.Fprintf(os.Stderr, "acl: unknown subcommand %q\n", os.Args[1])
		os.Exit(2)
	}
}

// An empty path yields no flows (lint accepts that).
func readFlows(path string) ([]eval.Flow, error) {
	if path == "" {
		return nil, nil
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	return eval.ParseFlows(file), nil
}

func printJSON(payload any) error {
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(encoded))
	return nil
}

func runEvaluate(args []string) error {
	fs := flag.NewFlagSet("evaluate", flag.ContinueOnError)
	rulesPath := fs.String("rules", "configs/ruleset.json", "path to the ordered ruleset JSON")
	flowsPath := fs.String("flows", "", "path to the flows NDJSON")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *flowsPath == "" {
		return fmt.Errorf("--flows is required")
	}

	loaded, err := ruleset.Load(*rulesPath)
	if err != nil {
		return err
	}
	flows, err := readFlows(*flowsPath)
	if err != nil {
		return err
	}

	decisions, _ := eval.Evaluate(flows, loaded.Rules, cidr.ParseIP)
	return printJSON(report.BuildEval(decisions))
}

func runLint(args []string) error {
	fs := flag.NewFlagSet("lint", flag.ContinueOnError)
	rulesPath := fs.String("rules", "configs/ruleset.json", "path to the ordered ruleset JSON")
	flowsPath := fs.String("flows", "", "optional flows NDJSON for the reachability pass")
	if err := fs.Parse(args); err != nil {
		return err
	}

	loaded, err := ruleset.Load(*rulesPath)
	if err != nil {
		return err
	}
	flows, err := readFlows(*flowsPath)
	if err != nil {
		return err
	}

	// The reachability pass needs to know which rules fired. With no flows every
	// live rule counts as never-fired.
	_, fired := eval.Evaluate(flows, loaded.Rules, cidr.ParseIP)
	an := eval.Analyze(loaded.Rules, fired)
	return printJSON(report.BuildLint(loaded.Warnings, an, len(loaded.Rules), loaded.RawCount))
}
