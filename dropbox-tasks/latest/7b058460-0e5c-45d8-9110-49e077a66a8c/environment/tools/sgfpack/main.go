package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: sgfpack repair|audit|export --root /app/workspace [--out /app/output/sgf-pack]")
		os.Exit(2)
	}
	cmd := os.Args[1]
	fs := flag.NewFlagSet(cmd, flag.ExitOnError)
	root := fs.String("root", "/app/workspace", "workspace root")
	out := fs.String("out", "/app/output/sgf-pack", "output pack")
	_ = fs.Parse(os.Args[2:])
	switch cmd {
	case "repair":
		if err := repairArchive(*root); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println("repaired", *root)
	case "audit":
		errs := auditArchive(*root)
		if len(errs) > 0 {
			for _, e := range errs {
				fmt.Fprintln(os.Stderr, e)
			}
			os.Exit(1)
		}
		fmt.Println("archive audit passed")
	case "export":
		if err := exportPack(*root, *out); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println("exported", *out)
	default:
		fmt.Fprintln(os.Stderr, "unknown command", cmd)
		os.Exit(2)
	}
}
