package main

import (
	"flag"
	"fmt"
	"os"

	"qxhub/eng"
)

func usage() {
	fmt.Fprintln(os.Stderr, "usage:")
	fmt.Fprintln(os.Stderr, "  lb_drive --arm <name> --out <path>")
	fmt.Fprintln(os.Stderr, "  lb_drive plan --arm <name> --out <path>")
	fmt.Fprintln(os.Stderr, "  lb_drive commit --plan <path> --cas <token> --out <path>")
	fmt.Fprintln(os.Stderr, "  lb_drive status | verify | replay | recover")
	os.Exit(2)
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		usage()
	}
	switch args[0] {
	case "plan":
		fs := flag.NewFlagSet("plan", flag.ExitOnError)
		arm := fs.String("arm", "", "arm name")
		out := fs.String("out", "", "plan path")
		_ = fs.Parse(args[1:])
		if *arm == "" || *out == "" {
			usage()
		}
		plan, err := eng.BuildPlan(*arm)
		if err != nil {
			fail(err)
		}
		if err := eng.WritePlan(*out, plan); err != nil {
			fail(err)
		}
		fmt.Println(plan.Token)
	case "commit":
		fs := flag.NewFlagSet("commit", flag.ExitOnError)
		planPath := fs.String("plan", "", "plan path")
		tok := fs.String("cas", "", "plan token")
		out := fs.String("out", "", "output path")
		_ = fs.Parse(args[1:])
		if *planPath == "" || *tok == "" || *out == "" {
			usage()
		}
		plan, err := eng.ReadPlan(*planPath)
		if err != nil {
			fail(err)
		}
		plan.Token = *tok
		if err := eng.CommitPlan(plan, *out); err != nil {
			fail(err)
		}
	case "status":
		doc, err := eng.Status()
		if err != nil {
			fail(err)
		}
		if err := eng.PrintJSON(doc); err != nil {
			fail(err)
		}
	case "verify":
		doc, err := eng.Verify()
		if err != nil {
			fail(err)
		}
		if err := eng.PrintJSON(doc); err != nil {
			fail(err)
		}
	case "replay":
		if err := eng.ReplayRegistry(); err != nil {
			fail(err)
		}
	case "recover":
		gen, seal, err := eng.RecoverCorrupt()
		if err != nil {
			fail(err)
		}
		fmt.Printf("%d %s\n", gen, seal)
	default:
		fs := flag.NewFlagSet("run", flag.ExitOnError)
		arm := fs.String("arm", "", "arm name")
		out := fs.String("out", "", "output path")
		_ = fs.Parse(args)
		if *arm == "" || *out == "" {
			usage()
		}
		if err := eng.RunArm(*arm, *out); err != nil {
			fail(err)
		}
	}
}
