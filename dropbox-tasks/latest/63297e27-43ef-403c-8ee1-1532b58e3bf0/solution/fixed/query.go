package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

type QueryMessage struct {
	Query string
	Fill  int
}

func (m *QueryMessage) payloadLen() int {
	return len(m.Query) + 1 + m.Fill
}

func (m *QueryMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *QueryMessage) Encode(dst []byte) ([]byte, error) {
	payloadLen := m.payloadLen()
	if payloadLen+4 > maxMessageBodyLen {
		return nil, fmt.Errorf("query: message body exceeds protocol maximum: %d", payloadLen)
	}
	dst = append(dst, msgTypeQuery)
	dst = wireio.AppendInt32(dst, int32(payloadLen+4))
	dst = append(dst, m.Query...)
	dst = append(dst, 0)
	return dst, nil
}
