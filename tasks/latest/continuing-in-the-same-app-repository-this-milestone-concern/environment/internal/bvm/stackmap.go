package bvm

import (
	"fmt"
	"strings"
)

// renderLocals renders a locals vector as [int, uninit, ref Dog].
func renderLocals(ts []Type) string {
	var parts []string
	for _, t := range ts {
		parts = append(parts, t.String())
	}
	return "[" + strings.Join(parts, ", ") + "]"
}

// OpcheckString runs the per-opcode transfer over the entry block of f as
// straight-line code, printing the stack before and after each instruction. It
// stops at the first type error. Cross-block merging is not performed here; that
// is verify's job.
func OpcheckString(m *Module, f *Func) string {
	var b strings.Builder
	st := entryState(f)
	blk := f.Blocks[0]
	for pc, in := range blk.Instrs {
		before := renderStack(st.stack)
		next, err := transfer(m, f, st, in)
		if err != nil {
			fmt.Fprintf(&b, "type error at %d: %s\n", pc, err.Error())
			return strings.TrimRight(b.String(), "\n")
		}
		fmt.Fprintf(&b, "%d %s :: %s => %s\n", pc, instrString(in), before, renderStack(next.stack))
		st = next
	}
	b.WriteString("ok")
	return b.String()
}

// StackmapString prints the abstract state (operand stack and locals) before
// each instruction of the entry block, then the final state, straight-line.
func StackmapString(m *Module, f *Func) string {
	var b strings.Builder
	st := entryState(f)
	blk := f.Blocks[0]
	for pc, in := range blk.Instrs {
		fmt.Fprintf(&b, "%d: stack=%s locals=%s\n", pc, renderStack(st.stack), renderLocals(st.locals))
		next, err := transfer(m, f, st, in)
		if err != nil {
			fmt.Fprintf(&b, "error at %d: %s\n", pc, err.Error())
			return strings.TrimRight(b.String(), "\n")
		}
		st = next
	}
	fmt.Fprintf(&b, "end: stack=%s locals=%s", renderStack(st.stack), renderLocals(st.locals))
	return b.String()
}
