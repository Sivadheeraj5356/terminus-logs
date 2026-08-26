package bvm

import (
	"fmt"
	"sort"
	"strings"
)

// fnv1a32 computes the 32-bit FNV-1a hash of s and renders it as 0x + eight
// lowercase hex digits.
func fnv1a32(s string) string {
	var h uint32 = 2166136261
	for i := 0; i < len(s); i++ {
		h ^= uint32(s[i])
		h *= 16777619
	}
	return fmt.Sprintf("0x%08x", h)
}

// instrString renders one instruction in its canonical text spelling.
func instrString(in Instr) string {
	switch in.Op {
	case "iconst", "load", "store", "bconst":
		return fmt.Sprintf("%s %d", in.Op, in.IntArg)
	case "fconst":
		return fmt.Sprintf("fconst %s", in.Str)
	case "new", "call", "br", "br_if", "newarray":
		return fmt.Sprintf("%s %s", in.Op, in.Str)
	case "getfield", "putfield":
		return fmt.Sprintf("%s %s %s", in.Op, in.Str, in.Field)
	default:
		return string(in.Op)
	}
}

// typeDeclString renders a struct declaration in canonical form.
func typeDeclString(env *TypeEnv, name string) string {
	var b strings.Builder
	b.WriteString("type ")
	b.WriteString(name)
	if par := env.parent[name]; par != "" {
		b.WriteString(" extends ")
		b.WriteString(par)
	}
	if fs := env.fields[name]; len(fs) > 0 {
		b.WriteString(" { ")
		var parts []string
		for _, f := range fs {
			parts = append(parts, f.Name+": "+f.Type.String())
		}
		b.WriteString(strings.Join(parts, ", "))
		b.WriteString(" }")
	}
	return b.String()
}

func funcSigString(f *Func) string {
	var ps []string
	for _, p := range f.Params {
		ps = append(ps, p.String())
	}
	return fmt.Sprintf("func %s(%s) -> %s", f.Name, strings.Join(ps, ", "), f.Ret.String())
}

// Disasm renders the whole module in its canonical text form (round-trips
// through Parse). Types are emitted sorted by name; functions in source order.
func Disasm(m *Module) string {
	var b strings.Builder
	names := append([]string(nil), m.Env.order...)
	sort.Strings(names)
	for _, n := range names {
		b.WriteString(typeDeclString(m.Env, n))
		b.WriteByte('\n')
	}
	for fi := range m.Funcs {
		f := &m.Funcs[fi]
		b.WriteString(funcSigString(f))
		b.WriteString(" {\n")
		if f.NLocals > 0 {
			fmt.Fprintf(&b, "  locals %d\n", f.NLocals)
		}
		for _, blk := range f.Blocks {
			b.WriteString(blk.Label)
			b.WriteString(":\n")
			for _, in := range blk.Instrs {
				b.WriteString("  ")
				b.WriteString(instrString(in))
				b.WriteByte('\n')
			}
		}
		b.WriteString("}\n")
	}
	return strings.TrimRight(b.String(), "\n")
}

// renderStack renders a slice of types as [a, b, c] or [].
func renderStack(ts []Type) string {
	var parts []string
	for _, t := range ts {
		parts = append(parts, t.String())
	}
	return "[" + strings.Join(parts, ", ") + "]"
}
