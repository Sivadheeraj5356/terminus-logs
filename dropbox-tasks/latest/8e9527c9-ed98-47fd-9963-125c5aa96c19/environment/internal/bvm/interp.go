package bvm

import (
	"fmt"
	"strconv"
	"strings"
)

type object struct {
	typeName string
	fields   map[string]value
}

type arrObj struct {
	elem  Type
	elems []value
}

type value struct {
	kind Kind
	i    int
	f    float64
	b    bool
	ref  *object // nil when kind==KNull
	arr  *arrObj
	name string // ref type name (for rendering / getfield resolution)
}

func vInt(i int) value     { return value{kind: KInt, i: i} }
func vFloat(f float64) value { return value{kind: KFloat, f: f} }
func vBool(b bool) value   { return value{kind: KBool, b: b} }
func vNull() value         { return value{kind: KNull} }

type trap struct{ reason string }

func (t trap) Error() string { return t.reason }

// defaultValue returns the zero value used for a freshly allocated field or
// array element of the given type.
func defaultValue(env *TypeEnv, t Type) value {
	switch t.Kind {
	case KInt:
		return vInt(0)
	case KFloat:
		return vFloat(0)
	case KBool:
		return vBool(false)
	case KRef, KNull:
		return vNull()
	case KArr:
		return value{kind: KArr, arr: &arrObj{elem: *t.Elem}}
	}
	return vNull()
}

func (m *Module) allocStruct(name string) *object {
	o := &object{typeName: name, fields: map[string]value{}}
	// gather fields from the root ancestor down (own order after inherited).
	chain := []string{}
	cur := name
	for cur != "" {
		chain = append([]string{cur}, chain...)
		cur = m.Env.parent[cur]
	}
	for _, c := range chain {
		for _, fld := range m.Env.fields[c] {
			o.fields[fld.Name] = defaultValue(m.Env, fld.Type)
		}
	}
	return o
}

const stepLimit = 2000000

type interp struct {
	m     *Module
	steps int
	trace *[]string
}

func (ip *interp) exec(f *Func, args []value) (value, error) {
	locals := make([]value, f.nlocals())
	for i := range locals {
		if i < len(args) {
			locals[i] = args[i]
		} else {
			locals[i] = vNull()
		}
	}
	var stack []value
	push := func(v value) { stack = append(stack, v) }
	pop := func() value {
		v := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		return v
	}
	bi := 0
	pc := 0
	for {
		if bi >= len(f.Blocks) {
			return value{}, trap{"fell off function"}
		}
		blk := f.Blocks[bi]
		if pc >= len(blk.Instrs) {
			return value{}, trap{"fell off block " + blk.Label}
		}
		in := blk.Instrs[pc]
		ip.steps++
		if ip.steps > stepLimit {
			return value{}, trap{"step limit exceeded"}
		}
		if ip.trace != nil {
			*ip.trace = append(*ip.trace, fmt.Sprintf("%s:%d %s", blk.Label, pc, instrString(in)))
		}
		goNext := true
		switch in.Op {
		case "iconst":
			push(vInt(in.IntArg))
		case "fconst":
			push(vFloat(in.FloatArg))
		case "bconst":
			push(vBool(in.IntArg == 1))
		case "null":
			push(vNull())
		case "pop":
			pop()
		case "dup":
			v := pop()
			push(v)
			push(v)
		case "swap":
			a := pop()
			b := pop()
			push(a)
			push(b)
		case "load":
			push(locals[in.IntArg])
		case "store":
			locals[in.IntArg] = pop()
		case "iadd", "isub", "imul":
			b := pop()
			a := pop()
			switch in.Op {
			case "iadd":
				push(vInt(a.i + b.i))
			case "isub":
				push(vInt(a.i - b.i))
			case "imul":
				push(vInt(a.i * b.i))
			}
		case "fadd", "fsub", "fmul":
			b := pop()
			a := pop()
			switch in.Op {
			case "fadd":
				push(vFloat(a.f + b.f))
			case "fsub":
				push(vFloat(a.f - b.f))
			case "fmul":
				push(vFloat(a.f * b.f))
			}
		case "icmp":
			b := pop()
			a := pop()
			push(vBool(a.i < b.i))
		case "fcmp":
			b := pop()
			a := pop()
			push(vBool(a.f < b.f))
		case "and":
			b := pop()
			a := pop()
			push(vBool(a.b && b.b))
		case "or":
			b := pop()
			a := pop()
			push(vBool(a.b || b.b))
		case "not":
			a := pop()
			push(vBool(!a.b))
		case "new":
			o := ip.m.allocStruct(in.Str)
			push(value{kind: KRef, ref: o, name: in.Str})
		case "getfield":
			r := pop()
			if r.kind == KNull || r.ref == nil {
				return value{}, trap{"getfield on null"}
			}
			push(r.ref.fields[in.Field])
		case "putfield":
			v := pop()
			r := pop()
			if r.kind == KNull || r.ref == nil {
				return value{}, trap{"putfield on null"}
			}
			r.ref.fields[in.Field] = v
		case "newarray":
			et, _, _ := parseTypeToks(splitFields(in.Str))
			n := pop()
			if n.i < 0 {
				return value{}, trap{"negative array length"}
			}
			elems := make([]value, n.i)
			for i := range elems {
				elems[i] = defaultValue(ip.m.Env, et)
			}
			push(value{kind: KArr, arr: &arrObj{elem: et, elems: elems}})
		case "aload":
			idx := pop()
			arr := pop()
			if arr.arr == nil {
				return value{}, trap{"aload on null array"}
			}
			if idx.i < 0 || idx.i >= len(arr.arr.elems) {
				return value{}, trap{"array index out of bounds"}
			}
			push(arr.arr.elems[idx.i])
		case "astore":
			v := pop()
			idx := pop()
			arr := pop()
			if arr.arr == nil {
				return value{}, trap{"astore on null array"}
			}
			if idx.i < 0 || idx.i >= len(arr.arr.elems) {
				return value{}, trap{"array index out of bounds"}
			}
			arr.arr.elems[idx.i] = v
		case "call":
			g, _ := ip.m.findFunc(in.Str)
			cargs := make([]value, len(g.Params))
			for i := len(g.Params) - 1; i >= 0; i-- {
				cargs[i] = pop()
			}
			rv, err := ip.exec(g, cargs)
			if err != nil {
				return value{}, err
			}
			if g.Ret.Kind != KVoid {
				push(rv)
			}
		case "br":
			ni, _ := f.findBlock(in.Str)
			bi = ni
			pc = 0
			goNext = false
		case "br_if":
			c := pop()
			if c.b {
				ni, _ := f.findBlock(in.Str)
				bi = ni
				pc = 0
			} else {
				bi = bi + 1
				pc = 0
			}
			goNext = false
		case "ret":
			if f.Ret.Kind == KVoid {
				return value{kind: KVoid}, nil
			}
			return pop(), nil
		}
		if goNext {
			pc++
		}
	}
}

func renderValue(v value) string {
	switch v.kind {
	case KInt:
		return strconv.Itoa(v.i)
	case KFloat:
		return strconv.FormatFloat(v.f, 'g', -1, 64)
	case KBool:
		if v.b {
			return "true"
		}
		return "false"
	case KVoid:
		return "void"
	case KNull:
		return "null"
	case KRef:
		if v.ref == nil {
			return "null"
		}
		return "ref " + v.ref.typeName
	case KArr:
		if v.arr == nil {
			return "null"
		}
		return fmt.Sprintf("arr %s[%d]", v.arr.elem.String(), len(v.arr.elems))
	}
	return "?"
}

// RunModule executes the entry function `main` and returns the result line.
func RunModule(m *Module, withTrace bool) (string, error) {
	f, ok := m.findFunc("main")
	if !ok {
		return "", errType("no main function")
	}
	if len(f.Params) != 0 {
		return "", errType("main must take no parameters")
	}
	ip := &interp{m: m}
	var tr []string
	if withTrace {
		ip.trace = &tr
	}
	v, err := ip.exec(f, nil)
	var tail string
	if err != nil {
		if t, ok := err.(trap); ok {
			tail = "trap: " + t.reason
		} else {
			return "", err
		}
	} else {
		tail = "result: " + renderValue(v)
	}
	if withTrace {
		return strings.Join(tr, "\n") + "\n" + tail, nil
	}
	return tail, nil
}
