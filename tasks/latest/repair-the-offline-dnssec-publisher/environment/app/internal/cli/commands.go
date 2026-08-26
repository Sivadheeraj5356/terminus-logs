package cli

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"zonepub/internal/config"
	"zonepub/internal/manifest"
	"zonepub/internal/publication"
)

const (
	ExitOK           = 0
	ExitUsage        = 2
	ExitInput        = 3
	ExitSigning      = 4
	ExitValidation   = 5
	ExitRecovery     = 6
)

func Run(args []string) int {
	if len(args) == 0 {
		usage()
		return ExitUsage
	}
	switch args[0] {
	case "publish":
		return runPublish(args[1:])
	case "import-snapshot":
		return runImportSnapshot(args[1:])
	case "inspect-manifest":
		return runInspectManifest(args[1:])
	case "-h", "--help", "help":
		usage()
		return ExitOK
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", args[0])
		usage()
		return ExitUsage
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, `zonepub - offline DNSSEC publication tool

Commands:
  publish           --workspace DIR --output-dir DIR [--epoch SEC]
  import-snapshot   --workspace DIR --snapshot FILE
  inspect-manifest  --manifest FILE [--format text|json]
`)
}

func runPublish(args []string) int {
	fs := flag.NewFlagSet("publish", flag.ContinueOnError)
	ws := fs.String("workspace", "", "workspace directory")
	out := fs.String("output-dir", "", "output directory")
	epoch := fs.Int64("epoch", 0, "fixed signing epoch (unix seconds)")
	fs.SetOutput(os.Stderr)
	if fs.Parse(args) != nil || *ws == "" || *out == "" {
		return ExitUsage
	}
	cfg, err := config.LoadWorkspace(*ws)
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		return ExitInput
	}
	if *epoch != 0 {
		cfg.Epoch = *epoch
	}
	if cfg.Epoch == 0 {
		fmt.Fprintf(os.Stderr, "epoch required\n")
		return ExitInput
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "output: %v\n", err)
		return ExitInput
	}
	pub := publication.NewPublisher(cfg, *ws, *out)
	code, err := pub.Publish()
	if err != nil {
		fmt.Fprintf(os.Stderr, "%v\n", err)
		return code
	}
	return ExitOK
}

func runImportSnapshot(args []string) int {
	fs := flag.NewFlagSet("import-snapshot", flag.ContinueOnError)
	ws := fs.String("workspace", "", "workspace directory")
	snap := fs.String("snapshot", "", "snapshot file")
	fs.SetOutput(os.Stderr)
	if fs.Parse(args) != nil || *ws == "" || *snap == "" {
		return ExitUsage
	}
	if err := manifest.ImportLegacySnapshot(*ws, *snap); err != nil {
		fmt.Fprintf(os.Stderr, "import: %v\n", err)
		return ExitInput
	}
	return ExitOK
}

func runInspectManifest(args []string) int {
	fs := flag.NewFlagSet("inspect-manifest", flag.ContinueOnError)
	mf := fs.String("manifest", "", "manifest path")
	format := fs.String("format", "text", "output format")
	fs.SetOutput(os.Stderr)
	if fs.Parse(args) != nil || *mf == "" {
		return ExitUsage
	}
	if err := manifest.Inspect(*mf, *format); err != nil {
		fmt.Fprintf(os.Stderr, "inspect: %v\n", err)
		return ExitInput
	}
	return ExitOK
}

func WorkspacePath(parts ...string) string {
	return filepath.Join(parts...)
}
