#!/bin/bash
set -euo pipefail
cd /app
mkdir -p /app/bin

cat > /app/internal/bvm/transfer.go <<'BVMEOF'
package bvm

// absState is an abstract machine state: the operand-stack types (top last) and
// the per-local types (KUninit for a not-yet-assigned slot).
type absState struct {
	stack  []Type
	locals []Type
}

func (s absState) clone() absState {
	ns := absState{
		stack:  append([]Type(nil), s.stack...),
		locals: append([]Type(nil), s.locals...),
	}
	return ns
}

// entryState builds the state on entry to a function: an empty stack and locals
// initialised to the parameter types followed by uninit declared slots.
func entryState(f *Func) absState {
	locals := make([]Type, f.nlocals())
	for i := range locals {
		if i < len(f.Params) {
			locals[i] = f.Params[i]
		} else {
			locals[i] = TUninit
		}
	}
	return absState{stack: nil, locals: locals}
}

func (s *absState) push(t Type) { s.stack = append(s.stack, t) }

func (s *absState) pop() (Type, bool) {
	if len(s.stack) == 0 {
		return Type{}, false
	}
	t := s.stack[len(s.stack)-1]
	s.stack = s.stack[:len(s.stack)-1]
	return t, true
}

// isTerminator reports whether op ends a basic block.
func isTerminator(op Op) bool {
	return op == "br" || op == "br_if" || op == "ret"
}

// transfer applies one instruction to a state, returning the successor state or
// a type error. It implements the per-opcode stack effect and type rules for
// every opcode, including the stack effect of the terminators (control flow is
// resolved by the caller from the terminator opcode).
func transfer(m *Module, f *Func, st absState, in Instr) (absState, error) {
	s := st.clone()
	env := m.Env
	popT := func() (Type, error) {
		t, ok := s.pop()
		if !ok {
			return Type{}, errType("stack underflow at %s", in.Op)
		}
		return t, nil
	}
	needSub := func(got, want Type, what string) error {
		if !env.isSubtype(got, want) {
			return errType("%s: expected %s, found %s", what, want, got)
		}
		return nil
	}

	switch in.Op {
	case "iconst":
		s.push(TInt)
	case "fconst":
		s.push(TFloat)
	case "bconst":
		s.push(TBool)
	case "null":
		s.push(TNull)
	case "pop":
		if _, err := popT(); err != nil {
			return st, err
		}
	case "dup":
		t, err := popT()
		if err != nil {
			return st, err
		}
		s.push(t)
		s.push(t)
	case "swap":
		a, err := popT()
		if err != nil {
			return st, err
		}
		b, err := popT()
		if err != nil {
			return st, err
		}
		s.push(a)
		s.push(b)
	case "load":
		n := in.IntArg
		if n < 0 || n >= len(s.locals) {
			return st, errType("load: local index %d out of range", n)
		}
		if s.locals[n].Kind == KUninit {
			return st, errType("local %d loaded before assignment", n)
		}
		s.push(s.locals[n])
	case "store":
		n := in.IntArg
		if n < 0 || n >= len(s.locals) {
			return st, errType("store: local index %d out of range", n)
		}
		t, err := popT()
		if err != nil {
			return st, err
		}
		s.locals[n] = t
	case "iadd", "isub", "imul":
		b, err := popT()
		if err != nil {
			return st, err
		}
		a, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(a, TInt, string(in.Op)); err != nil {
			return st, err
		}
		if err := needSub(b, TInt, string(in.Op)); err != nil {
			return st, err
		}
		s.push(TInt)
	case "fadd", "fsub", "fmul":
		b, err := popT()
		if err != nil {
			return st, err
		}
		a, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(a, TFloat, string(in.Op)); err != nil {
			return st, err
		}
		if err := needSub(b, TFloat, string(in.Op)); err != nil {
			return st, err
		}
		s.push(TFloat)
	case "icmp":
		b, err := popT()
		if err != nil {
			return st, err
		}
		a, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(a, TInt, "icmp"); err != nil {
			return st, err
		}
		if err := needSub(b, TInt, "icmp"); err != nil {
			return st, err
		}
		s.push(TBool)
	case "fcmp":
		b, err := popT()
		if err != nil {
			return st, err
		}
		a, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(a, TFloat, "fcmp"); err != nil {
			return st, err
		}
		if err := needSub(b, TFloat, "fcmp"); err != nil {
			return st, err
		}
		s.push(TBool)
	case "and", "or":
		b, err := popT()
		if err != nil {
			return st, err
		}
		a, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(a, TBool, string(in.Op)); err != nil {
			return st, err
		}
		if err := needSub(b, TBool, string(in.Op)); err != nil {
			return st, err
		}
		s.push(TBool)
	case "not":
		a, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(a, TBool, "not"); err != nil {
			return st, err
		}
		s.push(TBool)
	case "new":
		if !env.known(in.Str) {
			return st, errType("new: unknown type %q", in.Str)
		}
		s.push(TRef(in.Str))
	case "getfield":
		r, err := popT()
		if err != nil {
			return st, err
		}
		if !env.known(in.Str) {
			return st, errType("getfield: unknown type %q", in.Str)
		}
		if err := needSub(r, TRef(in.Str), "getfield receiver"); err != nil {
			return st, err
		}
		ft, ok := env.lookupField(in.Str, in.Field)
		if !ok {
			return st, errType("getfield: type %s has no field %s", in.Str, in.Field)
		}
		s.push(ft)
	case "putfield":
		v, err := popT()
		if err != nil {
			return st, err
		}
		r, err := popT()
		if err != nil {
			return st, err
		}
		if !env.known(in.Str) {
			return st, errType("putfield: unknown type %q", in.Str)
		}
		if err := needSub(r, TRef(in.Str), "putfield receiver"); err != nil {
			return st, err
		}
		ft, ok := env.lookupField(in.Str, in.Field)
		if !ok {
			return st, errType("putfield: type %s has no field %s", in.Str, in.Field)
		}
		if err := needSub(v, ft, "putfield value"); err != nil {
			return st, err
		}
	case "newarray":
		et, n, perr := parseTypeToks(splitFields(in.Str))
		if perr != nil || n == 0 {
			return st, errType("newarray: bad element type %q", in.Str)
		}
		lv, e := popT()
		if e != nil {
			return st, e
		}
		if err := needSub(lv, TInt, "newarray length"); err != nil {
			return st, err
		}
		s.push(TArr(et))
	case "aload":
		idx, err := popT()
		if err != nil {
			return st, err
		}
		arr, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(idx, TInt, "aload index"); err != nil {
			return st, err
		}
		if arr.Kind != KArr {
			return st, errType("aload: expected an array, found %s", arr)
		}
		s.push(*arr.Elem)
	case "astore":
		v, err := popT()
		if err != nil {
			return st, err
		}
		idx, err := popT()
		if err != nil {
			return st, err
		}
		arr, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(idx, TInt, "astore index"); err != nil {
			return st, err
		}
		if arr.Kind != KArr {
			return st, errType("astore: expected an array, found %s", arr)
		}
		if err := needSub(v, *arr.Elem, "astore value"); err != nil {
			return st, err
		}
	case "call":
		g, ok := m.findFunc(in.Str)
		if !ok {
			return st, errType("call: unknown function %q", in.Str)
		}
		args := make([]Type, len(g.Params))
		for i := len(g.Params) - 1; i >= 0; i-- {
			a, err := popT()
			if err != nil {
				return st, err
			}
			args[i] = a
		}
		for i := range g.Params {
			if err := needSub(args[i], g.Params[i], "call argument"); err != nil {
				return st, err
			}
		}
		if g.Ret.Kind != KVoid {
			s.push(g.Ret)
		}
	case "br":
		// no stack effect
	case "br_if":
		c, err := popT()
		if err != nil {
			return st, err
		}
		if err := needSub(c, TBool, "br_if condition"); err != nil {
			return st, err
		}
	case "ret":
		if f.Ret.Kind == KVoid {
			if len(s.stack) != 0 {
				return st, errType("ret: stack must be empty for a void function")
			}
		} else {
			v, err := popT()
			if err != nil {
				return st, err
			}
			if err := needSub(v, f.Ret, "ret value"); err != nil {
				return st, err
			}
			if len(s.stack) != 0 {
				return st, errType("ret: operand stack must be empty after the return value")
			}
		}
	default:
		return st, errType("transfer: unhandled opcode %q", in.Op)
	}
	return s, nil
}

func splitFields(s string) []string {
	var out []string
	cur := ""
	for _, r := range s {
		if r == ' ' || r == '\t' {
			if cur != "" {
				out = append(out, cur)
				cur = ""
			}
			continue
		}
		cur += string(r)
	}
	if cur != "" {
		out = append(out, cur)
	}
	return out
}
BVMEOF

cat > /app/internal/bvm/cfg.go <<'BVMEOF'
package bvm

import (
	"fmt"
	"strings"
)

// successors returns the labels of the blocks that control may transfer to from
// block index bi, in a fixed order. A `br L` yields [L]; a `br_if L` yields the
// taken target L followed by the fall-through block (the textually next block);
// a `ret` yields no successors.
func (f *Func) successors(bi int) ([]string, error) {
	blk := f.Blocks[bi]
	if len(blk.Instrs) == 0 {
		return nil, errType("block %s is empty", blk.Label)
	}
	last := blk.Instrs[len(blk.Instrs)-1]
	if !isTerminator(last.Op) {
		return nil, errType("block %s does not end in a terminator", blk.Label)
	}
	switch last.Op {
	case "br":
		if _, ok := f.findBlock(last.Str); !ok {
			return nil, errType("br to unknown block %q", last.Str)
		}
		return []string{last.Str}, nil
	case "br_if":
		if _, ok := f.findBlock(last.Str); !ok {
			return nil, errType("br_if to unknown block %q", last.Str)
		}
		if bi+1 >= len(f.Blocks) {
			return nil, errType("br_if in last block %s has no fall-through", blk.Label)
		}
		return []string{last.Str, f.Blocks[bi+1].Label}, nil
	case "ret":
		return nil, nil
	}
	return nil, errType("unreachable")
}

// reachableSet returns the set of block labels reachable from the entry block.
func (f *Func) reachableSet() (map[string]bool, error) {
	seen := map[string]bool{}
	if len(f.Blocks) == 0 {
		return seen, nil
	}
	var visit func(label string) error
	visit = func(label string) error {
		if seen[label] {
			return nil
		}
		seen[label] = true
		bi, _ := f.findBlock(label)
		succ, err := f.successors(bi)
		if err != nil {
			return err
		}
		for _, s := range succ {
			if err := visit(s); err != nil {
				return err
			}
		}
		return nil
	}
	if err := visit(f.Blocks[0].Label); err != nil {
		return nil, err
	}
	return seen, nil
}

// CFGString renders the control-flow graph of a function.
func CFGString(f *Func) (string, error) {
	var b strings.Builder
	fmt.Fprintf(&b, "entry: %s\n", f.Blocks[0].Label)
	for bi := range f.Blocks {
		succ, err := f.successors(bi)
		if err != nil {
			return "", err
		}
		if len(succ) == 0 {
			fmt.Fprintf(&b, "%s -> exit\n", f.Blocks[bi].Label)
		} else {
			fmt.Fprintf(&b, "%s -> %s\n", f.Blocks[bi].Label, strings.Join(succ, ", "))
		}
	}
	return strings.TrimRight(b.String(), "\n"), nil
}
BVMEOF

