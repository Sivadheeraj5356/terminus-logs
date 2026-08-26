package proto

import "framewire/internal/wireio"

type BindMessage struct {
	Portal       string
	Statement    string
	ParamFormats []int16
	Params       []Param
	ResultFormat []int16
}

func (m *BindMessage) payloadLen() int {
	n := len(m.Portal) + 1 + len(m.Statement) + 1
	n += 2 + 2*len(m.ParamFormats)
	n += 2
	for _, p := range m.Params {
		n += 4 + p.length()
	}
	n += 2 + 2*len(m.ResultFormat)
	return n
}

func (m *BindMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *BindMessage) Encode(dst []byte) ([]byte, error) {
	payloadLen := m.payloadLen()
	dst = append(dst, msgTypeBind)
	dst = wireio.AppendInt32(dst, int32(payloadLen+4))
	dst = append(dst, m.Portal...)
	dst = append(dst, 0)
	dst = append(dst, m.Statement...)
	dst = append(dst, 0)
	dst = wireio.AppendUint16(dst, uint16(len(m.ParamFormats)))
	for _, f := range m.ParamFormats {
		dst = wireio.AppendUint16(dst, uint16(f))
	}
	dst = wireio.AppendUint16(dst, uint16(len(m.Params)))
	for _, p := range m.Params {
		dst = wireio.AppendInt32(dst, int32(p.length()))
		dst = append(dst, p.Value...)
	}
	dst = wireio.AppendUint16(dst, uint16(len(m.ResultFormat)))
	for _, f := range m.ResultFormat {
		dst = wireio.AppendUint16(dst, uint16(f))
	}
	return dst, nil
}
