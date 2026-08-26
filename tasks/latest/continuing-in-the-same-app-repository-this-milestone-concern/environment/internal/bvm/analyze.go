package bvm

import (
	"fmt"
	"strings"
)

// maxStack returns the greatest operand-stack depth reached at any program
// point of any reachable block, using the per-block entry states produced by
// the verification fixpoint. Because a block's entry height is inherited from
// its predecessors, the depth is measured relative to that entry state, and the
// maximum is taken over every reachable block and every path.
func maxStack(m *Module, f *Func, res verifyResult) (int, error) {
	reach, err := f.reachableSet()
	if err != nil {
		return 0, err
	}
	best := 0
	for bi := range f.Blocks {
		if !reach[f.Blocks[bi].Label] {
			continue
		}
		entry, ok := res.inState[bi]
		if !ok {
			continue
		}
		st := absState{locals: entry.locals}
		if len(st.stack) > best {
			best = len(st.stack)
		}
		for _, in := range f.Blocks[bi].Instrs {
			ns, err := transfer(m, f, st, in)
			if err != nil {
				return 0, err
			}
			st = ns
			if len(st.stack) > best {
				best = len(st.stack)
			}
		}
	}
	return best, nil
}

// AnalyzeString reports, per function, the reachable and dead blocks and the
// maximum operand-stack depth.
func AnalyzeString(m *Module) (string, error) {
	var b strings.Builder
	for fi := range m.Funcs {
		f := &m.Funcs[fi]
		reach, err := f.reachableSet()
		if err != nil {
			return "", err
		}
		var live, dead []string
		for bi := range f.Blocks {
			lbl := f.Blocks[bi].Label
			if reach[lbl] {
				live = append(live, lbl)
			} else {
				dead = append(dead, lbl)
			}
		}
		fmt.Fprintf(&b, "func %s:\n", f.Name)
		fmt.Fprintf(&b, "  reachable: %s\n", strings.Join(live, ", "))
		if len(dead) == 0 {
			b.WriteString("  dead: (none)\n")
		} else {
			fmt.Fprintf(&b, "  dead: %s\n", strings.Join(dead, ", "))
		}
		res := verifyFunc(m, f)
		if !res.ok {
			b.WriteString("  max_stack: n/a\n")
			continue
		}
		ms, err := maxStack(m, f, res)
		if err != nil {
			return "", err
		}
		fmt.Fprintf(&b, "  max_stack: %d\n", ms)
	}
	return strings.TrimRight(b.String(), "\n"), nil
}
