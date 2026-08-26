package bvm

import (
	"errors"
	"fmt"
	"os"
	"sort"
	"strings"
)

// ErrUsage is returned for an unknown or missing subcommand.
var ErrUsage = errors.New("usage: bvm <parse|disasm|opcheck|stackmap|cfg|dom|verify|run|trace|analyze|report|batch> ...")

func flagMap(args []string) map[string]string {
	m := map[string]string{}
	for i := 0; i+1 < len(args); i += 2 {
		if strings.HasPrefix(args[i], "--") {
			m[args[i][2:]] = args[i+1]
		}
	}
	return m
}

func loadModule(fm map[string]string) (*Module, error) {
	path := fm["module"]
	if path == "" {
		return nil, fmt.Errorf("missing --module")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(string(data))
}

func pickFunc(m *Module, fm map[string]string) (*Func, error) {
	name := fm["func"]
	if name == "" {
		name = "main"
	}
	f, ok := m.findFunc(name)
	if !ok {
		return nil, fmt.Errorf("no such function %q", name)
	}
	return f, nil
}

// Run dispatches a subcommand and returns (stdout, exitCode, error).
func Run(args []string) (string, int, error) {
	if len(args) == 0 {
		return "", 2, ErrUsage
	}
	cmd := args[0]
	fm := flagMap(args[1:])

	switch cmd {
	case "parse":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		names := append([]string(nil), m.Env.order...)
		sort.Strings(names)
		var b strings.Builder
		fmt.Fprintf(&b, "types: %s\n", strings.Join(names, ", "))
		for fi := range m.Funcs {
			f := &m.Funcs[fi]
			fmt.Fprintf(&b, "%s : blocks=%d locals=%d\n", funcSigString(f), len(f.Blocks), f.NLocals)
		}
		fmt.Fprintf(&b, "checksum: %s", fnv1a32(Disasm(m)))
		return b.String(), 0, nil

	case "disasm":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		return Disasm(m), 0, nil

	case "opcheck":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		f, err := pickFunc(m, fm)
		if err != nil {
			return "", 2, err
		}
		return OpcheckString(m, f), 0, nil

	case "stackmap":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		f, err := pickFunc(m, fm)
		if err != nil {
			return "", 2, err
		}
		return StackmapString(m, f), 0, nil

	case "cfg":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		f, err := pickFunc(m, fm)
		if err != nil {
			return "", 2, err
		}
		out, err := CFGString(f)
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil

	case "dom":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		f, err := pickFunc(m, fm)
		if err != nil {
			return "", 2, err
		}
		out, err := DomString(f)
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil

	case "verify":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		return VerifyModule(m), 0, nil

	case "analyze":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		out, err := AnalyzeString(m)
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil

	case "report":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		out, err := ReportModule(m)
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil

	case "run":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		out, err := RunModule(m, false)
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil

	case "trace":
		m, err := loadModule(fm)
		if err != nil {
			return "", 2, err
		}
		out, err := RunModule(m, true)
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil

	case "batch":
		out, err := RunBatch(fm["manifest"])
		if err != nil {
			return "", 2, err
		}
		return out, 0, nil
	}
	return "", 2, ErrUsage
}
