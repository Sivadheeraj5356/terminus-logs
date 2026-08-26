package main

import (
	"encoding/json"
	"fmt"
	"os"

	"pitctl/pipe"
)

func usage() {
	fmt.Fprintln(os.Stderr, "usage: pitctl materialize --fold <id> --out <path>")
	fmt.Fprintln(os.Stderr, "       pitctl status --fold <id>")
	fmt.Fprintln(os.Stderr, "       pitctl verify --fold <id> --report <path>")
	os.Exit(2)
}

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	cmd := os.Args[1]
	args := os.Args[2:]
	switch cmd {
	case "materialize":
		fold, out := "", ""
		for i := 0; i < len(args); i++ {
			if args[i] == "--fold" && i+1 < len(args) {
				fold = args[i+1]
				i++
			} else if args[i] == "--out" && i+1 < len(args) {
				out = args[i+1]
				i++
			}
		}
		if fold == "" || out == "" {
			usage()
		}
		if _, err := pipe.Materialize(fold, out); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "status":
		fold := ""
		for i := 0; i < len(args); i++ {
			if args[i] == "--fold" && i+1 < len(args) {
				fold = args[i+1]
				i++
			}
		}
		if fold == "" {
			usage()
		}
		payload, err := pipe.Status(fold)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		enc := json.NewEncoder(os.Stdout)
		_ = enc.Encode(payload)
	case "verify":
		fold, report := "", ""
		for i := 0; i < len(args); i++ {
			if args[i] == "--fold" && i+1 < len(args) {
				fold = args[i+1]
				i++
			} else if args[i] == "--report" && i+1 < len(args) {
				report = args[i+1]
				i++
			}
		}
		if fold == "" || report == "" {
			usage()
		}
		payload, err := pipe.Verify(fold, report)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		enc := json.NewEncoder(os.Stdout)
		_ = enc.Encode(payload)
		if ok, _ := payload["ok"].(bool); !ok {
			os.Exit(1)
		}
	default:
		usage()
	}
}
