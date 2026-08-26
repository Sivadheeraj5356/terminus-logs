package main

import (
	"fmt"
	"os"

	"splicekit/internal/runner"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: splicectl reset|run <id>|status|publish")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "reset":
		if err := runner.Reset(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "run":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "usage: splicectl run <scenario_id>")
			os.Exit(2)
		}
		rep, err := runner.Run(os.Args[2])
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Printf("ran %s served=%d rejected=%d gen=%d\n", rep.ScenarioID, len(rep.Served), len(rep.Rejected), rep.Generation)
	case "status":
		s, err := runner.Status()
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println(s)
	case "publish":
		if err := runner.Publish(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println("published")
	default:
		fmt.Fprintln(os.Stderr, "unknown verb")
		os.Exit(2)
	}
}
