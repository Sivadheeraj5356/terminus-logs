package proto

import "framewire/internal/wireio"

type ParseMessage struct {
	Name      string
	Query     string
	Fill      int
	ParamOIDs []uint32
}

func (m *ParseMessage) payloadLen() int {
	return len(m.Name) + 1 + len(m.Query) + 1 + m.Fill + 2 + 4*len(m.ParamOIDs)
}

func (m *ParseMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *ParseMessage) Encode(dst []byte) ([]byte, error) {
	dst, err := finishHeader(dst, msgTypeParse, m.payloadLen())
	if err != nil {
		return nil, err
	}
	dst = append(dst, m.Name...)
	dst = append(dst, 0)
	dst = append(dst, m.Query...)
	dst = append(dst, 0)
	dst = wireio.AppendUint16(dst, uint16(len(m.ParamOIDs)))
	for _, oid := range m.ParamOIDs {
		dst = wireio.AppendUint32(dst, oid)
	}
	return dst, nil
}
