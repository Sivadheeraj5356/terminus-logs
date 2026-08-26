#!/bin/bash
set -euo pipefail
cd /app
mkdir -p /app/bin

cat > /app/internal/bvm/types.go <<'BVMEOF'
package bvm

import "fmt"

// Kind enumerates the categories of value types in the ISA.
type Kind int

const (
	KInt Kind = iota
	KFloat
	KBool
	KNull  // the null reference; subtype of every ref type
	KRef   // a named struct reference type
	KArr   // an array type with an element type
	KVoid  // only valid as a function return type
	KUninit // an unassigned local slot (definite-assignment bottom)
)

// Type is a value type. For KRef, Name holds the struct name. For KArr, Elem
// holds the element type.
type Type struct {
	Kind Kind
	Name string
	Elem *Type
}

var (
	TInt   = Type{Kind: KInt}
	TFloat = Type{Kind: KFloat}
	TBool  = Type{Kind: KBool}
	TNull  = Type{Kind: KNull}
	TVoid  = Type{Kind: KVoid}
	TUninit = Type{Kind: KUninit}
)

func TRef(name string) Type { return Type{Kind: KRef, Name: name} }
func TArr(elem Type) Type   { e := elem; return Type{Kind: KArr, Elem: &e} }

// String renders a type in its canonical spelling.
func (t Type) String() string {
	switch t.Kind {
	case KInt:
		return "int"
	case KFloat:
		return "float"
	case KBool:
		return "bool"
	case KNull:
		return "null"
	case KVoid:
		return "void"
	case KUninit:
		return "uninit"
	case KRef:
		return "ref " + t.Name
	case KArr:
		return "arr " + t.Elem.String()
	}
	return "?"
}

// Equal reports structural equality of two types.
func (t Type) Equal(o Type) bool {
	if t.Kind != o.Kind {
		return false
	}
	switch t.Kind {
	case KRef:
		return t.Name == o.Name
	case KArr:
		return t.Elem.Equal(*o.Elem)
	}
	return true
}

func (t Type) isRef() bool { return t.Kind == KRef || t.Kind == KNull }

// TypeEnv holds the declared struct hierarchy and their fields.
type TypeEnv struct {
	parent map[string]string  // struct -> immediate parent ("" if none => root obj)
	fields map[string][]Field // struct -> own fields (not inherited)
	order  []string           // declared struct names in source order
}

// Field is a named typed field of a struct.
type Field struct {
	Name string
	Type Type
}

func newTypeEnv() *TypeEnv {
	return &TypeEnv{parent: map[string]string{}, fields: map[string][]Field{}}
}

func (e *TypeEnv) known(name string) bool {
	_, ok := e.parent[name]
	return ok
}

// ancestors returns the chain from name up to the implicit root, inclusive of
// name and the root sentinel "obj". e.g. Dog -> [Dog, Animal, obj].
func (e *TypeEnv) ancestors(name string) []string {
	var out []string
	cur := name
	for cur != "" {
		out = append(out, cur)
		cur = e.parent[cur]
	}
	out = append(out, "obj")
	return out
}

// isDescendant reports whether a is a (non-strict) descendant of b in the
// struct hierarchy (a <: b for ref types). "obj" is the root of every struct.
func (e *TypeEnv) isDescendant(a, b string) bool {
	if b == "obj" {
		return true
	}
	for _, x := range e.ancestors(a) {
		if x == b {
			return true
		}
	}
	return false
}

// commonAncestor returns the nearest common ancestor of two struct names,
// walking up from a until a name that is an ancestor of b is found. Returns
// "obj" when the only shared ancestor is the implicit root.
func (e *TypeEnv) commonAncestor(a, b string) string {
	for _, x := range e.ancestors(a) {
		if e.isDescendant(b, x) {
			return x
		}
	}
	return "obj"
}

// lookupField finds a field by name, searching name's own fields then its
// ancestors' fields. Returns the field type and whether it was found.
func (e *TypeEnv) lookupField(name, field string) (Type, bool) {
	cur := name
	for cur != "" {
		for _, f := range e.fields[cur] {
			if f.Name == field {
				return f.Type, true
			}
		}
		cur = e.parent[cur]
	}
	return Type{}, false
}

// isSubtype reports whether s <: t under the ISA subtyping rules:
//   - identical types are subtypes;
//   - null is a subtype of every ref type;
//   - ref S <: ref T iff S is a (non-strict) descendant of T;
//   - arrays are INVARIANT: arr S <: arr T iff S == T exactly;
//   - primitives are subtypes only of themselves.
func (e *TypeEnv) isSubtype(s, t Type) bool {
	if s.Equal(t) {
		return true
	}
	if s.Kind == KNull && t.Kind == KRef {
		return true
	}
	if s.Kind == KRef && t.Kind == KRef {
		return e.isDescendant(s.Name, t.Name)
	}
	return false
}

// lub computes the least upper bound of two stack-slot types. It returns the
// merged type and true, or false when the two types have no common type (an
// incompatible join).
func (e *TypeEnv) lub(a, b Type) (Type, bool) {
	if a.Equal(b) {
		return a, true
	}
	if a.isRef() && b.isRef() {
		if a.Kind == KNull {
			return b, true
		}
		if b.Kind == KNull {
			return a, true
		}
		anc := e.commonAncestor(a.Name, b.Name)
		if anc == "obj" {
			return TRef("obj"), true
		}
		return TRef(anc), true
	}
	return Type{}, false
}

// lubLocal merges two local-slot types for the definite-assignment analysis.
// uninit is absorbing: a local is definitely assigned only if assigned on every
// incoming path, so merging uninit with anything yields uninit; two incompatible
// concrete types also make the slot unusable (top == uninit).
func (e *TypeEnv) lubLocal(a, b Type) (Type, bool) {
	if a.Kind == KUninit || b.Kind == KUninit {
		return TUninit, true
	}
	if lu, ok := e.lub(a, b); ok {
		return lu, true
	}
	return TUninit, true
}

func errType(format string, args ...interface{}) error {
	return fmt.Errorf(format, args...)
}
BVMEOF

cat > /app/internal/bvm/verify.go <<'BVMEOF'
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
	if len(cur.stack) != len(incoming.stack) {
		return *cur, false, fmt.Sprintf("stack height mismatch (%d vs %d)", len(cur.stack), len(incoming.stack))
	}
	merged := absState{
		stack:  make([]Type, len(cur.stack)),
		locals: make([]Type, len(cur.locals)),
	}
	for i := range cur.stack {
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
				in[si] = merged
				have[si] = true
				dirty[si] = true
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
BVMEOF

cat > /app/internal/bvm/dom.go <<'BVMEOF'
package bvm

import (
	"fmt"
	"strings"
)

// domInfo is the result of dominator analysis: for each reachable block index,
// its immediate dominator's block index (entry maps to itself).
type domInfo struct {
	idom  map[int]int
	order []int // reachable block indices in source order
}

// computeDom computes immediate dominators using the Cooper-Harvey-Kennedy
// iterative algorithm over the reverse-postorder of the reachable CFG.
func computeDom(f *Func) (domInfo, error) {
	reach, err := f.reachableSet()
	if err != nil {
		return domInfo{}, err
	}
	succIdx := map[int][]int{}
	for bi := range f.Blocks {
		if !reach[f.Blocks[bi].Label] {
			continue
		}
		ss, err := f.successors(bi)
		if err != nil {
			return domInfo{}, err
		}
		for _, sl := range ss {
			si, _ := f.findBlock(sl)
			succIdx[bi] = append(succIdx[bi], si)
		}
	}
	entry := 0
	var post []int
	seen := map[int]bool{}
	var dfs func(int)
	dfs = func(bi int) {
		seen[bi] = true
		for _, s := range succIdx[bi] {
			if !seen[s] {
				dfs(s)
			}
		}
		post = append(post, bi)
	}
	dfs(entry)
	rpoNum := map[int]int{}
	for i, bi := range post {
		rpoNum[bi] = i // postorder index; entry has the largest
	}
	preds := map[int][]int{}
	for bi, ss := range succIdx {
		for _, s := range ss {
			preds[s] = append(preds[s], bi)
		}
	}
	idom := map[int]int{entry: entry}
	intersect := func(a, b int) int {
		for a != b {
			for rpoNum[a] < rpoNum[b] {
				a = idom[a]
			}
			for rpoNum[b] < rpoNum[a] {
				b = idom[b]
			}
		}
		return a
	}
	rpo := make([]int, 0, len(post))
	for i := len(post) - 1; i >= 0; i-- {
		rpo = append(rpo, post[i])
	}
	changed := true
	for changed {
		changed = false
		for _, b := range rpo {
			if b == entry {
				continue
			}
			newIdom := -1
			for _, p := range preds[b] {
				if _, ok := idom[p]; !ok {
					continue
				}
				if newIdom == -1 {
					newIdom = p
				} else {
					newIdom = intersect(p, newIdom)
				}
			}
			if newIdom != -1 {
				if cur, ok := idom[b]; !ok || cur != newIdom {
					idom[b] = newIdom
					changed = true
				}
			}
		}
	}
	var order []int
	for bi := range f.Blocks {
		if reach[f.Blocks[bi].Label] {
			order = append(order, bi)
		}
	}
	return domInfo{idom: idom, order: order}, nil
}

// DomString renders the dominator tree of a function.
func DomString(f *Func) (string, error) {
	d, err := computeDom(f)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	for _, bi := range d.order {
		if bi == 0 {
			fmt.Fprintf(&b, "idom %s = (root)\n", f.Blocks[bi].Label)
		} else {
			fmt.Fprintf(&b, "idom %s = %s\n", f.Blocks[bi].Label, f.Blocks[d.idom[bi]].Label)
		}
	}
	return strings.TrimRight(b.String(), "\n"), nil
}
BVMEOF

cat > /app/internal/bvm/analyze.go <<'BVMEOF'
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
		st := entry.clone()
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
BVMEOF

