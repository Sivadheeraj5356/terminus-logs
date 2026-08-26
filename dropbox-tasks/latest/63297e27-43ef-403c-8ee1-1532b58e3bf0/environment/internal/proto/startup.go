package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

const protocolVersion = 196608

type StartupParam struct {
	Key   string
	Value string
}

type StartupMessage struct {
	Parameters []StartupParam
}

func (m *StartupMessage) payloadLen() int {
	n := 4
	for _, p := range m.Parameters {
		n += len(p.Key) + 1 + len(p.Value) + 1
	}
	return n + 1
}

func (m *StartupMessage) Encode(dst []byte) ([]byte, error) {
	frameLen := m.payloadLen() + 4
	if frameLen > maxMessageBodyLen {
		return nil, fmt.Errorf("framing: startup message too large to encode: %d", m.payloadLen())
	}
	dst = wireio.AppendInt32(dst, int32(frameLen))
	dst = wireio.AppendUint32(dst, protocolVersion)
	for _, p := range m.Parameters {
		dst = append(dst, p.Key...)
		dst = append(dst, 0)
		dst = append(dst, p.Value...)
		dst = append(dst, 0)
	}
	dst = append(dst, 0)
	return dst, nil
}
