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
			if p := e.parent[x]; p != "" {
				return p
			}
			return "obj"
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
	if a.Kind == KUninit {
		return b, true
	}
	if b.Kind == KUninit {
		return a, true
	}
	if lu, ok := e.lub(a, b); ok {
		return lu, true
	}
	return TUninit, true
}

func errType(format string, args ...interface{}) error {
	return fmt.Errorf(format, args...)
}
