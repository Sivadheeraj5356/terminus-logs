package bvm

// Op is an opcode mnemonic.
type Op string

// Instr is a single decoded instruction. IntArg / FloatArg / Str carry the
// immediate operands depending on the opcode.
type Instr struct {
	Op       Op
	IntArg   int
	FloatArg float64
	Str      string // label target, type name, or field-owning type
	Field    string // field name for getfield/putfield
	Line     int    // source line (for diagnostics)
}

// Block is a basic block: a label and a straight-line list of instructions
// ending in a terminator.
type Block struct {
	Label  string
	Instrs []Instr
}

// Func is a function: signature, extra-local count, and blocks in source order.
type Func struct {
	Name    string
	Params  []Type
	Ret     Type
	NLocals int // number of declared locals beyond the parameters
	Blocks  []Block
	blockAt map[string]int // label -> index in Blocks
}

// nlocals returns the total number of local slots (params + declared).
func (f *Func) nlocals() int { return len(f.Params) + f.NLocals }

// Module is a parsed module: the type environment and the functions.
type Module struct {
	Env   *TypeEnv
	Funcs []Func
	funcAt map[string]int
}

func (m *Module) findFunc(name string) (*Func, bool) {
	if i, ok := m.funcAt[name]; ok {
		return &m.Funcs[i], true
	}
	return nil, false
}

func (f *Func) findBlock(label string) (int, bool) {
	i, ok := f.blockAt[label]
	return i, ok
}
