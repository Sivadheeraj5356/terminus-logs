package main

import (
	"errors"
	"fmt"
	"os"

	"passenger-rebooking-engine/internal/export"
	"passenger-rebooking-engine/internal/stage"
)

const version = "passenger-rebooking-engine/1.0.0"

func main() {
	if err := dispatch(os.Args); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		if errors.Is(err, export.ErrSnapshotMissing) || errors.Is(err, export.ErrLedgerMissing) {
			os.Exit(2)
		}
		os.Exit(2)
	}
}

func dispatch(args []string) error {
	if len(args) < 2 {
		if err := stage.Run(); err != nil {
			return err
		}
		return export.Publish()
	}
	switch args[1] {
	case "build":
		if err := stage.Run(); err != nil {
			return err
		}
		return export.Publish()
	case "stage":
		return stage.Run()
	case "export":
		return export.Publish()
	case "version":
		fmt.Println(version)
		return nil
	default:
		return fmt.Errorf("unknown subcommand: %s", args[1])
	}
}
