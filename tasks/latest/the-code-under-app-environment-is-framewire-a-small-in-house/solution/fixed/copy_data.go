package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

type CopyDataMessage struct {
	Data        []byte
	DeclaredLen int
}

func (m *CopyDataMessage) payloadLen() int {
	if m.DeclaredLen > 0 {
		return m.DeclaredLen
	}
	return len(m.Data)
}

func (m *CopyDataMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *CopyDataMessage) Encode(dst []byte) ([]byte, error) {
	payloadLen := m.payloadLen()
	if payloadLen+4 > maxMessageBodyLen {
		return nil, fmt.Errorf("copydata: message body exceeds protocol maximum: %d", payloadLen)
	}
	dst = append(dst, msgTypeCopyData)
	dst = wireio.AppendInt32(dst, int32(payloadLen+4))
	dst = append(dst, m.Data...)
	return dst, nil
}
