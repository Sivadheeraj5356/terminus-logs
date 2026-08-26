package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"helm-chart-coalesce/internal/chartwalk"
	"helm-chart-coalesce/internal/export"
)

func Run(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("unknown command")
	}
	switch args[0] {
	case "resolve":
		return runResolve(args[1:])
	default:
		return fmt.Errorf("unknown command %q", args[0])
	}
}

func runResolve(args []string) error {
	var chartDir, outPath string
	var valuesFiles, setArgs []string
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--chart":
			i++
			if i >= len(args) {
				return fmt.Errorf("missing --chart")
			}
			chartDir = args[i]
		case "--out":
			i++
			if i >= len(args) {
				return fmt.Errorf("missing --out")
			}
			outPath = args[i]
		case "--values":
			i++
			if i >= len(args) {
				return fmt.Errorf("missing --values")
			}
			valuesFiles = append(valuesFiles, args[i])
		case "--set":
			i++
			if i >= len(args) {
				return fmt.Errorf("missing --set")
			}
			setArgs = append(setArgs, args[i])
		default:
			return fmt.Errorf("unknown argument %q", args[i])
		}
	}
	if chartDir == "" || outPath == "" {
		return fmt.Errorf("usage: helmvals resolve --chart PATH [--values FILE ...] [--set key=value ...] --out PATH")
	}
	manifest, err := chartwalk.Resolve(chartwalk.Input{
		ChartDir: chartDir, ValuesFiles: valuesFiles, SetArgs: setArgs,
	})
	if err != nil {
		return err
	}
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if err := writeOut(outPath, data); err != nil {
		return err
	}
	snap := "/app/state/helmvals-resolve-snapshot.json"
	return writeOut(snap, data)
}

func writeOut(path string, data []byte) error {
	if dir := filepath.Dir(path); dir != "" && dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	return os.WriteFile(path, data, 0o644)
}

var _ export.Manifest
