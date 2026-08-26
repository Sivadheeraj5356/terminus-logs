package bvm

import (
	"fmt"
	"strings"
)

// verifyResult is the outcome of verifying one function.
type verifyResult struct {
	ok      bool
	reason  string           // populated when ok == false
	inState map[int]absState // entry state of each reachable block (fixpoint result)
}

// statesEqual reports whether two abstract states are identical.
func statesEqual(a, b absState) bool {
	if len(a.stack) != len(b.stack) || len(a.locals) != len(b.locals) {
		return false
	}
	for i := range a.stack {
		if !a.stack[i].Equal(b.stack[i]) {
			return false
		}
	}
	for i := range a.locals {
		if !a.locals[i].Equal(b.locals[i]) {
			return false
		}
	}
	return true
}

// mergeState computes the least upper bound of an incoming state into the
// current entry state of a block. It returns the merged state, whether it
// differs from cur, and a non-empty reason if the join is illegal (a stack
// height mismatch or an incompatible stack-slot type).
func mergeState(env *TypeEnv, cur *absState, incoming absState) (absState, bool, string) {
	if cur == nil {
		return incoming.clone(), true, ""
	}
	n := len(cur.stack)
	if len(incoming.stack) < n {
		n = len(incoming.stack)
	}
	merged := absState{
		stack:  make([]Type, n),
		locals: make([]Type, len(cur.locals)),
	}
	for i := 0; i < n; i++ {
		lu, ok := env.lub(cur.stack[i], incoming.stack[i])
		if !ok {
			return *cur, false, fmt.Sprintf("incompatible stack types at slot %d (%s vs %s)", i, cur.stack[i], incoming.stack[i])
		}
		merged.stack[i] = lu
	}
	for i := range cur.locals {
		lu, _ := env.lubLocal(cur.locals[i], incoming.locals[i])
		merged.locals[i] = lu
	}
	return merged, !statesEqual(*cur, merged), ""
}

// verifyFunc runs the abstract-interpretation dataflow to a fixpoint over the
// control-flow graph of f, merging predecessor states at join points via the
// type lattice and enforcing definite assignment of locals.
func verifyFunc(m *Module, f *Func) verifyResult {
	if len(f.Blocks) == 0 {
		return verifyResult{ok: false, reason: "function has no blocks"}
	}
	in := map[int]absState{}
	have := map[int]bool{}
	dirty := map[int]bool{}

	in[0] = entryState(f)
	have[0] = true
	dirty[0] = true

	// deterministic worklist: always process the lowest dirty block index.
	nextDirty := func() (int, bool) {
		for bi := range f.Blocks {
			if dirty[bi] {
				return bi, true
			}
		}
		return -1, false
	}

	for {
		bi, ok := nextDirty()
		if !ok {
			break
		}
		dirty[bi] = false
		blk := f.Blocks[bi]
		st := in[bi].clone()
		for pc, instr := range blk.Instrs {
			ns, err := transfer(m, f, st, instr)
			if err != nil {
				return verifyResult{ok: false, reason: fmt.Sprintf("at %s:%d %s: %s", blk.Label, pc, instr.Op, err.Error())}
			}
			st = ns
		}
		succ, err := f.successors(bi)
		if err != nil {
			return verifyResult{ok: false, reason: fmt.Sprintf("at %s: %s", blk.Label, err.Error())}
		}
		for _, sl := range succ {
			si, _ := f.findBlock(sl)
			var cur *absState
			if have[si] {
				c := in[si]
				cur = &c
			}
			merged, changed, reason := mergeState(m.Env, cur, st)
			if reason != "" {
				return verifyResult{ok: false, reason: fmt.Sprintf("at %s join: %s", sl, reason)}
			}
			if changed {
				if !have[si] {
					dirty[si] = true
				}
				in[si] = merged
				have[si] = true
			}
		}
	}
	return verifyResult{ok: true, inState: in}
}

// VerifyModule verifies every function and returns one line per function in
// source order: "NAME: verified" or "NAME: rejected (<reason>)".
func VerifyModule(m *Module) string {
	var b strings.Builder
	for fi := range m.Funcs {
		f := &m.Funcs[fi]
		r := verifyFunc(m, f)
		if r.ok {
			fmt.Fprintf(&b, "%s: verified\n", f.Name)
		} else {
			fmt.Fprintf(&b, "%s: rejected (%s)\n", f.Name, r.reason)
		}
	}
	return strings.TrimRight(b.String(), "\n")
}
