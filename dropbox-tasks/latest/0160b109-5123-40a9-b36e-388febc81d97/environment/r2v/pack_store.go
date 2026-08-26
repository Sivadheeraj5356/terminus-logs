package r2v

type PackState struct {
	Blob  []byte
	Stamp uint32
}

func NewPack() *PackState {
	return &PackState{Blob: nil, Stamp: 0}
}

func (p *PackState) Clone() *PackState {
	if p == nil {
		return NewPack()
	}
	out := &PackState{Stamp: p.Stamp}
	out.Blob = append([]byte(nil), p.Blob...)
	return out
}

// Bind applies the package durable bind path used by the conversion engine.
func Bind(dst *PackState, src *PackState, stampB uint32) uint32 {
	return pack_b2(dst, src, stampB)
}
