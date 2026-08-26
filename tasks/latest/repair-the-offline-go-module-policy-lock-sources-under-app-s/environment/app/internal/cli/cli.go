package cli

import (
	"flag"
	"fmt"
	"os"

	"corp.example/modlock/seal"
	"corp.example/modlock/internal/lockfile"
	"corp.example/modlock/remap"
	"corp.example/modlock/emit"
	"corp.example/modlock/internal/resolve"
	"corp.example/modlock/internal/types"
)

func Main(args []string) int {
	if len(args) == 0 {
		printUsage()
		return 2
	}
	switch args[0] {
	case "resolve":
		return cmdResolve(args[1:])
	case "report":
		return cmdReport(args[1:])
	case "reindex":
		return cmdReindex(args[1:])
	case "migrate-lock":
		return cmdMigrate(args[1:])
	case "verify":
		return cmdVerify(args[1:])
	case "--help", "-h", "help":
		printUsage()
		return 0
	default:
		fmt.Fprintf(os.Stderr, "unknown subcommand: %s\n", args[0])
		printUsage()
		return 2
	}
}

func printUsage() {
	fmt.Println(`modpolicylock resolve  --request PATH --goos OS --goarch ARCH --lock OUT --db PATH [--root PATH]
modpolicylock report   --request PATH --goos OS --goarch ARCH --report OUT --db PATH [--root PATH]
modpolicylock reindex  --mirror PATH --db PATH [--resume]
modpolicylock migrate-lock --in PATH --out PATH
modpolicylock verify   --lock PATH --report PATH`)
}

func cmdResolve(args []string) int {
	fs := flag.NewFlagSet("resolve", flag.ExitOnError)
	request := fs.String("request", "", "")
	goos := fs.String("goos", "linux", "")
	goarch := fs.String("goarch", "amd64", "")
	lockOut := fs.String("lock", "", "")
	dbPath := fs.String("db", "/app/var/policy-index/policy.db", "")
	root := fs.String("root", "/app", "")
	_ = fs.Parse(args)

	modules, rev, err := resolve.BuildGraph(resolve.Options{
		RequestPath: *request, Goos: *goos, Goarch: *goarch, DBPath: *dbPath, Root: *root,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := lockfile.Write(*lockOut, *goos, *goarch, rev, modules); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdReport(args []string) int {
	fs := flag.NewFlagSet("report", flag.ExitOnError)
	request := fs.String("request", "", "")
	goos := fs.String("goos", "linux", "")
	goarch := fs.String("goarch", "amd64", "")
	reportOut := fs.String("report", "", "")
	dbPath := fs.String("db", "/app/var/policy-index/policy.db", "")
	root := fs.String("root", "/app", "")
	_ = fs.Parse(args)

	modules, rev, err := emit.EmitView(emit.Options{
		RequestPath: *request, Goos: *goos, Goarch: *goarch, DBPath: *dbPath, Root: *root,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := lockfile.Write(*reportOut, *goos, *goarch, rev, modules); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdReindex(args []string) int {
	fs := flag.NewFlagSet("reindex", flag.ExitOnError)
	mirror := fs.String("mirror", "/app/var/module-mirror", "")
	dbPath := fs.String("db", "/app/var/policy-index/policy.db", "")
	resume := fs.Bool("resume", false, "")
	_ = fs.Parse(args)
	if err := seal.Reindex(*mirror, *dbPath, *resume); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdMigrate(args []string) int {
	fs := flag.NewFlagSet("migrate-lock", flag.ExitOnError)
	inPath := fs.String("in", "", "")
	outPath := fs.String("out", "", "")
	_ = fs.Parse(args)
	if err := remap.MigrateLock(*inPath, *outPath); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdVerify(args []string) int {
	fs := flag.NewFlagSet("verify", flag.ExitOnError)
	lockPath := fs.String("lock", "", "")
	reportPath := fs.String("report", "", "")
	_ = fs.Parse(args)
	lock, err := lockfile.Read(*lockPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	rep, err := lockfile.Read(*reportPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if lock.ResolutionDigest != rep.ResolutionDigest {
		fmt.Fprintln(os.Stderr, "digest mismatch")
		return 1
	}
	for _, m := range lock.Modules {
		rm, ok := findModule(rep.Modules, m.Path)
		if !ok || rm.Version != m.Version || rm.Source != m.Source || rm.PolicyDecision != m.PolicyDecision {
			fmt.Fprintln(os.Stderr, "graph mismatch:", m.Path)
			return 1
		}
	}
	if len(lock.Modules) != len(rep.Modules) {
		fmt.Fprintln(os.Stderr, "graph mismatch: module count")
		return 1
	}
	return 0
}

func findModule(mods []types.ModuleEntry, path string) (types.ModuleEntry, bool) {
	for _, m := range mods {
		if m.Path == path {
			return m, true
		}
	}
	return types.ModuleEntry{}, false
}
