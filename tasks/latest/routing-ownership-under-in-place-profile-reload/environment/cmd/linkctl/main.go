package main

import (
	"flag"
	"fmt"
	"os"

	"linkenv/engine"
	"linkenv/emit"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: linkctl <boot|reconfigure|recover|purge-history> ...")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "boot":
		runBoot(os.Args[2:])
	case "reconfigure":
		runApply(os.Args[2:])
	case "recover":
		runRecover(os.Args[2:])
	case "purge-history":
		fmt.Fprintln(os.Stderr, "purge-history disabled in offline lab")
		os.Exit(2)
	default:
		fmt.Fprintln(os.Stderr, "unknown subcommand")
		os.Exit(2)
	}
}

func runBoot(args []string) {
	fs := flag.NewFlagSet("boot", flag.ExitOnError)
	profile := fs.String("profile", "alpha", "profile name")
	root := fs.String("root", "/app/var/state", "state directory")
	out := fs.String("out", "/app/output", "output directory")
	_ = fs.Parse(args)
	prof, err := engine.LoadProfile("/app/data/topology_w3", *profile)
	if err != nil {
		die(err)
	}
	_ = emit.ResetJournal(*out)
	st := engine.NewStore(*root)
	if err := st.ColdBoot(prof, "/app/data/topology_w3/foreign_rows.json", "/app/var/grant_feed.jsonl", *out); err != nil {
		die(err)
	}
}

func runApply(args []string) {
	fs := flag.NewFlagSet("apply", flag.ExitOnError)
	profile := fs.String("profile", "alpha", "profile name")
	root := fs.String("root", "/app/var/state", "state directory")
	out := fs.String("out", "/app/output", "output directory")
	_ = fs.Parse(args)
	prof, err := engine.LoadProfile("/app/data/topology_w3", *profile)
	if err != nil {
		die(err)
	}
	st := engine.NewStore(*root)
	if err := st.ApplyProfile(prof, "/app/data/topology_w3/foreign_rows.json", "/app/var/grant_feed.jsonl", *out); err != nil {
		die(err)
	}
}

func runRecover(args []string) {
	fs := flag.NewFlagSet("recover", flag.ExitOnError)
	root := fs.String("root", "/app/var/state", "state directory")
	out := fs.String("out", "/app/output", "output directory")
	profile := fs.String("profile", "beta", "profile label for probes")
	_ = fs.Parse(args)
	st := engine.NewStore(*root)
	if err := st.Recover(*out, *profile); err != nil {
		die(err)
	}
}

func die(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
