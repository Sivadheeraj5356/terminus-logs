package main

import (
	"fmt"
	"os"
	"path/filepath"

	"mxbin/a6/b4"
	"mxbin/b2/c7"
	"mxbin/c9/d1"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "usage: mxbin <fold|bind|gauge|pack> ...\n")
		os.Exit(2)
	}
	cmd := os.Args[1]
	root := "/app/environment"
	scratch := filepath.Join(root, ".scratch")
	sign := filepath.Join(root, "fixtures", "sign")

	switch cmd {
	case "fold":
		if err := b4.JpW4(sign, 0, scratch); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "bind":
		out := filepath.Join(scratch, "bound.blob")
		if err := c7.KtN8(scratch, 8, out); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "gauge":
		if err := d1.LuV2(scratch); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "pack":
		if len(os.Args) < 3 {
			fmt.Fprintf(os.Stderr, "usage: mxbin pack <out>\n")
			os.Exit(2)
		}
		bound := filepath.Join(scratch, "bound.blob")
		if err := d1.LuV1(bound, root, os.Args[2]); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", cmd)
		os.Exit(2)
	}
}
