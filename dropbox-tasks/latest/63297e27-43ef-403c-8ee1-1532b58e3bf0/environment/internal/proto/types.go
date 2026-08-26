package proto

const (
	FormatText   = 0
	FormatBinary = 1
)

const (
	OIDInt4 = 23
	OIDText = 25
	OIDBool = 16
)

type Param struct {
	Value       []byte
	DeclaredLen int
}

func (p Param) length() int {
	if p.DeclaredLen > 0 {
		return p.DeclaredLen
	}
	return len(p.Value)
}
