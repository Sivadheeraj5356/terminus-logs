package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

const msgTypeFormatCodes = 'W'

type FormatCodesMessage struct {
	Count int
}

func (m *FormatCodesMessage) payloadLen() int {
	return 2 + 2*m.Count
}

func (m *FormatCodesMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *FormatCodesMessage) Encode(dst []byte) ([]byte, error) {
	if m.Count > 0xffff {
		return nil, fmt.Errorf("formats: format code count exceeds protocol maximum: %d", m.Count)
	}
	dst, err := finishHeader(dst, msgTypeFormatCodes, m.payloadLen())
	if err != nil {
		return nil, err
	}
	dst = wireio.AppendUint16(dst, uint16(m.Count))
	for i := 0; i < m.Count; i++ {
		dst = wireio.AppendUint16(dst, 0)
	}
	return dst, nil
}
