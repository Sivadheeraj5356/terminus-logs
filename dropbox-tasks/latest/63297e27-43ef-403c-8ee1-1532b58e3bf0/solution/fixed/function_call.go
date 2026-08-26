package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

const msgTypeFunctionCall = 'F'

type FunctionCallMessage struct {
	Args        []byte
	DeclaredLen int
}

func (m *FunctionCallMessage) payloadLen() int {
	if m.DeclaredLen > 0 {
		return 4 + m.DeclaredLen
	}
	return 4 + len(m.Args)
}

func (m *FunctionCallMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *FunctionCallMessage) Encode(dst []byte) ([]byte, error) {
	payloadLen := m.payloadLen()
	if payloadLen+4 > maxMessageBodyLen {
		return nil, fmt.Errorf("funcall: message body exceeds protocol maximum: %d", payloadLen)
	}
	dst = append(dst, msgTypeFunctionCall)
	dst = wireio.AppendInt32(dst, int32(payloadLen+4))
	dst = wireio.AppendUint32(dst, 0)
	dst = append(dst, m.Args...)
	return dst, nil
}
