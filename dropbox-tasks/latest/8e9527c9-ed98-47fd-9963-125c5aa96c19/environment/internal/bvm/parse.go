package bvm

import (
	"fmt"
	"strconv"
	"strings"
)

// Parse reads a module from its text form. It is deliberately strict: a
// structurally malformed module is an error. Parsing does no type checking.
func Parse(src string) (*Module, error) {
	p := &parser{lines: strings.Split(src, "\n")}
	return p.parseModule()
}

type parser struct {
	lines []string
	i     int
}

func stripComment(s string) string {
	if idx := strings.IndexByte(s, '#'); idx >= 0 {
		s = s[:idx]
	}
	return s
}

func (p *parser) parseModule() (*Module, error) {
	m := &Module{Env: newTypeEnv(), funcAt: map[string]int{}}
	for p.i < len(p.lines) {
		raw := stripComment(p.lines[p.i])
		line := strings.TrimSpace(raw)
		if line == "" {
			p.i++
			continue
		}
		switch {
		case strings.HasPrefix(line, "type "):
			if err := p.parseType(m, line); err != nil {
				return nil, err
			}
			p.i++
		case strings.HasPrefix(line, "func "):
			f, err := p.parseFunc(m)
			if err != nil {
				return nil, err
			}
			if _, dup := m.funcAt[f.Name]; dup {
				return nil, errType("duplicate function %q", f.Name)
			}
			m.funcAt[f.Name] = len(m.Funcs)
			m.Funcs = append(m.Funcs, *f)
		default:
			return nil, errType("line %d: unexpected %q", p.i+1, line)
		}
	}
	// validate type parents exist.
	for _, name := range m.Env.order {
		par := m.Env.parent[name]
		if par != "" && !m.Env.known(par) {
			return nil, errType("type %q extends unknown type %q", name, par)
		}
	}
	return m, nil
}

func (p *parser) parseType(m *Module, line string) error {
	rest := strings.TrimSpace(strings.TrimPrefix(line, "type "))
	body := ""
	if idx := strings.IndexByte(rest, '{'); idx >= 0 {
		if !strings.HasSuffix(rest, "}") {
			return errType("line %d: malformed field block", p.i+1)
		}
		body = strings.TrimSpace(rest[idx+1 : len(rest)-1])
		rest = strings.TrimSpace(rest[:idx])
	}
	toks := strings.Fields(rest)
	if len(toks) == 0 {
		return errType("line %d: missing type name", p.i+1)
	}
	name := toks[0]
	parent := ""
	if len(toks) >= 3 && toks[1] == "extends" {
		parent = toks[2]
	} else if len(toks) != 1 {
		return errType("line %d: malformed type declaration", p.i+1)
	}
	if m.Env.known(name) {
		return errType("duplicate type %q", name)
	}
	m.Env.parent[name] = parent
	m.Env.order = append(m.Env.order, name)
	var fields []Field
	if body != "" {
		for _, part := range strings.Split(body, ",") {
			part = strings.TrimSpace(part)
			if part == "" {
				continue
			}
			colon := strings.IndexByte(part, ':')
			if colon < 0 {
				return errType("line %d: malformed field %q", p.i+1, part)
			}
			fname := strings.TrimSpace(part[:colon])
			ft, _, err := parseTypeToks(strings.Fields(strings.TrimSpace(part[colon+1:])))
			if err != nil {
				return err
			}
			fields = append(fields, Field{Name: fname, Type: ft})
		}
	}
	m.Env.fields[name] = fields
	return nil
}

// parseTypeToks parses a type expression from the front of toks and returns the
// type plus the number of tokens consumed.
func parseTypeToks(toks []string) (Type, int, error) {
	if len(toks) == 0 {
		return Type{}, 0, errType("expected a type")
	}
	switch toks[0] {
	case "int":
		return TInt, 1, nil
	case "float":
		return TFloat, 1, nil
	case "bool":
		return TBool, 1, nil
	case "void":
		return TVoid, 1, nil
	case "ref":
		if len(toks) < 2 {
			return Type{}, 0, errType("ref requires a type name")
		}
		return TRef(toks[1]), 2, nil
	case "arr":
		elem, n, err := parseTypeToks(toks[1:])
		if err != nil {
			return Type{}, 0, err
		}
		return TArr(elem), n + 1, nil
	}
	return Type{}, 0, errType("unknown type %q", toks[0])
}

func (p *parser) parseFunc(m *Module) (*Func, error) {
	header := strings.TrimSpace(stripComment(p.lines[p.i]))
	// func NAME(params) -> RET {
	if !strings.HasSuffix(header, "{") {
		return nil, errType("line %d: function header must end with '{'", p.i+1)
	}
	header = strings.TrimSpace(strings.TrimSuffix(header, "{"))
	open := strings.IndexByte(header, '(')
	close := strings.IndexByte(header, ')')
	if open < 0 || close < 0 || close < open {
		return nil, errType("line %d: malformed function header", p.i+1)
	}
	name := strings.TrimSpace(header[len("func "):open])
	paramStr := strings.TrimSpace(header[open+1 : close])
	after := strings.TrimSpace(header[close+1:])
	if !strings.HasPrefix(after, "->") {
		return nil, errType("line %d: expected '->' return type", p.i+1)
	}
	rt, _, err := parseTypeToks(strings.Fields(strings.TrimSpace(after[2:])))
	if err != nil {
		return nil, err
	}
	f := &Func{Name: name, Ret: rt, blockAt: map[string]int{}}
	if paramStr != "" {
		for _, ps := range strings.Split(paramStr, ",") {
			pt, _, err := parseTypeToks(strings.Fields(strings.TrimSpace(ps)))
			if err != nil {
				return nil, err
			}
			f.Params = append(f.Params, pt)
		}
	}
	p.i++ // consume header

	var cur *Block
	commit := func() {
		if cur != nil {
			f.blockAt[cur.Label] = len(f.Blocks)
			f.Blocks = append(f.Blocks, *cur)
			cur = nil
		}
	}
	for p.i < len(p.lines) {
		line := strings.TrimSpace(stripComment(p.lines[p.i]))
		if line == "" {
			p.i++
			continue
		}
		if line == "}" {
			p.i++
			commit()
			for i := range f.Blocks {
				f.blockAt[f.Blocks[i].Label] = i
			}
			if len(f.Blocks) == 0 {
				return nil, errType("function %q has no blocks", name)
			}
			for _, blk := range f.Blocks {
				if len(blk.Instrs) == 0 {
					return nil, errType("block %s is empty", blk.Label)
				}
				for j, ins := range blk.Instrs {
					if isTerminator(ins.Op) && j != len(blk.Instrs)-1 {
						return nil, errType("block %s: terminator %s must be the last instruction", blk.Label, ins.Op)
					}
				}
				if !isTerminator(blk.Instrs[len(blk.Instrs)-1].Op) {
					return nil, errType("block %s does not end in a terminator", blk.Label)
				}
			}
			return f, nil
		}
		if strings.HasPrefix(line, "locals ") {
			n, err := strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "locals ")))
			if err != nil || n < 0 {
				return nil, errType("line %d: bad locals count", p.i+1)
			}
			f.NLocals = n
			p.i++
			continue
		}
		if strings.HasSuffix(line, ":") && !strings.ContainsAny(line, " \t") {
			commit()
			label := strings.TrimSuffix(line, ":")
			cur = &Block{Label: label}
			p.i++
			continue
		}
		// instruction
		if cur == nil {
			return nil, errType("line %d: instruction outside a block", p.i+1)
		}
		ins, err := parseInstr(line, p.i+1)
		if err != nil {
			return nil, err
		}
		cur.Instrs = append(cur.Instrs, ins)
		p.i++
	}
	return nil, errType("function %q not closed", name)
}

func parseInstr(line string, lineNo int) (Instr, error) {
	toks := strings.Fields(line)
	op := Op(toks[0])
	args := toks[1:]
	ins := Instr{Op: op, Line: lineNo}
	need := func(n int) error {
		if len(args) != n {
			return errType("line %d: %s expects %d operand(s)", lineNo, op, n)
		}
		return nil
	}
	switch op {
	case "iconst", "load", "store":
		if err := need(1); err != nil {
			return ins, err
		}
		v, err := strconv.Atoi(args[0])
		if err != nil {
			return ins, errType("line %d: bad integer operand", lineNo)
		}
		ins.IntArg = v
	case "bconst":
		if err := need(1); err != nil {
			return ins, err
		}
		if args[0] != "0" && args[0] != "1" {
			return ins, errType("line %d: bconst wants 0 or 1", lineNo)
		}
		ins.IntArg, _ = strconv.Atoi(args[0])
	case "fconst":
		if err := need(1); err != nil {
			return ins, err
		}
		v, err := strconv.ParseFloat(args[0], 64)
		if err != nil {
			return ins, errType("line %d: bad float operand", lineNo)
		}
		ins.FloatArg = v
		ins.Str = args[0]
	case "new", "call", "br", "br_if":
		if err := need(1); err != nil {
			return ins, err
		}
		ins.Str = args[0]
	case "newarray":
		if len(args) < 1 {
			return ins, errType("line %d: newarray expects an element type", lineNo)
		}
		ins.Str = strings.Join(args, " ")
	case "getfield", "putfield":
		if err := need(2); err != nil {
			return ins, err
		}
		ins.Str = args[0]
		ins.Field = args[1]
	case "null", "pop", "dup", "swap", "iadd", "isub", "imul",
		"fadd", "fsub", "fmul", "icmp", "fcmp", "and", "or", "not",
		"aload", "astore", "ret":
		if err := need(0); err != nil {
			return ins, err
		}
	default:
		return ins, errType("line %d: unknown opcode %q", lineNo, op)
	}
	return ins, nil
}

func fmtInt(n int) string { return fmt.Sprintf("%d", n) }
