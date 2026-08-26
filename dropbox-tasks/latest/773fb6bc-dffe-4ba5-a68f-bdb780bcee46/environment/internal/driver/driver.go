package driver

import (
	"fmt"
	"os"

	"github.com/lab/cvstack/internal/args"
	"github.com/lab/cvstack/internal/ops"
	"github.com/lab/cvstack/internal/plumb"
)

func Run(argv []string) int {
	cmd, err := args.Parse(argv)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	root := args.Root()
	switch cmd.Name {
	case "copy":
		sample := cmd.Flag["sample"]
		dest := cmd.Flag["dest"]
		if sample == "" || dest == "" {
			fmt.Fprintln(os.Stderr, "copy requires --sample and --dest")
			return 2
		}
		if err := plumb.CopySample(root, sample, dest); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		return 0
	case "status":
		ws := cmd.Flag["workspace"]
		if ws == "" {
			fmt.Fprintln(os.Stderr, "status requires --workspace")
			return 2
		}
		if err := ops.RunStatus(ws); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		return 0
	case "invariant":
		ws := cmd.Flag["workspace"]
		if ws == "" {
			fmt.Fprintln(os.Stderr, "invariant requires --workspace")
			return 2
		}
		if err := ops.ClearOutputs(ws); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		if err := ops.RunInvariant(ws); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		return 0
	case "recover":
		ws := cmd.Flag["workspace"]
		if ws == "" {
			fmt.Fprintln(os.Stderr, "recover requires --workspace")
			return 2
		}
		if err := ops.RunRecover(ws); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		return 0
	case "read-replay":
		ws := cmd.Flag["workspace"]
		events := cmd.Flag["events"]
		if ws == "" || events == "" {
			fmt.Fprintln(os.Stderr, "read-replay requires --workspace and --events")
			return 2
		}
		if err := ops.RunRead(ws, events); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
		return 0
	case "help", "-h", "--help":
		fmt.Println(ops.FormatHelp())
		return 0
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", cmd.Name)
		fmt.Fprintln(os.Stderr, ops.FormatHelp())
		return 2
	}
}
