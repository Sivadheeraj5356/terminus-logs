package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/privco/ctpki/internal/bundlewalk"
	"github.com/privco/ctpki/internal/ledgerpublish"
	"github.com/privco/ctpki/internal/trustmatrix"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: ctpki <attest|publish>")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "attest":
		fs := flag.NewFlagSet("attest", flag.ExitOnError)
		bundle := fs.String("bundle", "", "migration bundle root")
		snap := fs.String("snapshot", "", "snap json path")
		report := fs.String("report", "", "disposition report json path")
		_ = fs.Parse(os.Args[2:])
		if *bundle == "" || *snap == "" || *report == "" {
			fmt.Fprintln(os.Stderr, "attest requires --bundle --snapshot and --report")
			os.Exit(2)
		}
		if err := bundlewalk.Run(*bundle, *snap); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if err := trustmatrix.Run(*bundle, *snap, *report); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "publish":
		fs := flag.NewFlagSet("publish", flag.ExitOnError)
		report := fs.String("report", "", "disposition report json path")
		snapshot := fs.String("snapshot", "", "merkle snapshot json path")
		out := fs.String("out", "", "trusted ledger json path")
		_ = fs.Parse(os.Args[2:])
		if *report == "" || *snapshot == "" || *out == "" {
			fmt.Fprintln(os.Stderr, "publish requires --report --snapshot and --out")
			os.Exit(2)
		}
		if err := ledgerpublish.WriteTrusted(*report, *snapshot, *out); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	default:
		fmt.Fprintln(os.Stderr, "unknown subcommand")
		os.Exit(2)
	}
}
