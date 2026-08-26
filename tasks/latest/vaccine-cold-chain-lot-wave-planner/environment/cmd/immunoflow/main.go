package main

import (
	"flag"
	"fmt"
	"os"

	"immunoflow/emit"
)

func main() {
	emit.EnsureDirs()
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "bench":
		if len(os.Args) < 3 || os.Args[2] != "reset" {
			fmt.Fprintln(os.Stderr, "usage: immunoflow bench reset")
			os.Exit(2)
		}
		must(emit.BenchReset())
	case "plan-wave":
		fs := flag.NewFlagSet("plan-wave", flag.ExitOnError)
		lab := fs.String("lab", "/app/data/immunolab", "")
		wave := fs.Int("wave", 3, "")
		out := fs.String("out", "/app/output/allocation_plan.json", "")
		_ = fs.Parse(os.Args[2:])
		must(emit.PlanWave(*lab, *wave, *out))
	case "bind-lanes":
		fs := flag.NewFlagSet("bind-lanes", flag.ExitOnError)
		wave := fs.Int("wave", 3, "")
		plan := fs.String("plan", "/app/output/allocation_plan.json", "")
		out := fs.String("out", "/app/output/coldchain_audit.json", "")
		_ = fs.Parse(os.Args[2:])
		must(emit.BindLanes(*wave, *plan, *out))
	case "schedule-doses":
		fs := flag.NewFlagSet("schedule-doses", flag.ExitOnError)
		lab := fs.String("lab", "/app/data/immunolab", "")
		d1 := fs.Int("dose1-wave", 3, "")
		_ = fs.Parse(os.Args[2:])
		must(emit.ScheduleDoses(*lab, *d1))
	case "reconcile-equity":
		fs := flag.NewFlagSet("reconcile-equity", flag.ExitOnError)
		lab := fs.String("lab", "/app/data/immunolab", "")
		plan := fs.String("plan", "/app/output/allocation_plan.json", "")
		_ = fs.Parse(os.Args[2:])
		must(emit.ReconcileEquity(*lab, *plan))
	case "project-infections":
		fs := flag.NewFlagSet("project-infections", flag.ExitOnError)
		lab := fs.String("lab", "/app/data/immunolab", "")
		plan := fs.String("plan", "/app/output/allocation_plan.json", "")
		_ = fs.Parse(os.Args[2:])
		must(emit.ProjectInfections(*lab, *plan))
	case "inspect":
		fs := flag.NewFlagSet("inspect", flag.ExitOnError)
		g := fs.Int("generation", 0, "")
		_ = fs.Parse(os.Args[2:])
		raw, err := emit.Inspect(*g)
		must(err)
		fmt.Print(string(raw))
	case "spoilage-replan":
		fs := flag.NewFlagSet("spoilage-replan", flag.ExitOnError)
		lab := fs.String("lab", "/app/data/immunolab", "")
		wave := fs.Int("wave", 3, "")
		_ = fs.Parse(os.Args[2:])
		must(emit.SpoilageReplan(*lab, *wave))
	default:
		usage()
		os.Exit(2)
	}
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: immunoflow bench reset | plan-wave | bind-lanes | schedule-doses | reconcile-equity | project-infections | inspect | spoilage-replan")
}
