package bvm

import (
	"fmt"
	"strings"
)

// ReportModule renders a per-function report (verification status, block count,
// max stack) followed by an FNV-1a-32 digest over the report body.
func ReportModule(m *Module) (string, error) {
	var lines []string
	lines = append(lines, fmt.Sprintf("types: %d  funcs: %d", len(m.Env.order), len(m.Funcs)))
	for fi := range m.Funcs {
		f := &m.Funcs[fi]
		res := verifyFunc(m, f)
		if !res.ok {
			lines = append(lines, fmt.Sprintf("func %s: rejected blocks=%d", f.Name, len(f.Blocks)))
			continue
		}
		ms, err := maxStack(m, f, res)
		if err != nil {
			return "", err
		}
		lines = append(lines, fmt.Sprintf("func %s: verified blocks=%d max_stack=%d", f.Name, len(f.Blocks), ms))
	}
	body := strings.Join(lines, "\n")
	return body + "\n" + "digest: " + fnv1a32(body), nil
}
