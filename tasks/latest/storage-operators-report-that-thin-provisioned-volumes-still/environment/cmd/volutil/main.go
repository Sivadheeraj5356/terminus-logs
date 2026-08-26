package main

import (
	"fmt"
	"os"
	"strconv"

	"slotmgr/internal/pipeline"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: volutil list | volutil run <output-dir> | volutil try")
		os.Exit(2)
	}
	root := os.Getenv("REPLAY_ROOT")
	if root == "" {
		root = "/app/environment"
	}
	switch os.Args[1] {
	case "list":
		sess, err := pipeline.SessionID(root)
		if err != nil {
			fmt.Fprintf(os.Stderr, "volutil: %v\n", err)
			os.Exit(1)
		}
		fmt.Println(sess)
	case "run":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "usage: volutil run <output-dir>")
			os.Exit(2)
		}
		cycle := 1
		if v := os.Getenv("CYCLE"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				cycle = n
			}
		}
		appendMode := os.Getenv("APPEND_EXPORT") == "1"
		if err := pipeline.RunPass(root, os.Args[2], cycle, appendMode); err != nil {
			fmt.Fprintf(os.Stderr, "volutil: %v\n", err)
			os.Exit(1)
		}
	case "try":
		out := os.Getenv("OUTPUT_DIR")
		if out == "" {
			out = "/app/output"
		}
		ok, err := pipeline.ViewsAligned(root, out)
		if err != nil || !ok {
			fmt.Fprintln(os.Stderr, "volutil: skew")
			os.Exit(1)
		}
	default:
		fmt.Fprintln(os.Stderr, "usage: volutil list | volutil run <output-dir> | volutil try")
		os.Exit(2)
	}
}
