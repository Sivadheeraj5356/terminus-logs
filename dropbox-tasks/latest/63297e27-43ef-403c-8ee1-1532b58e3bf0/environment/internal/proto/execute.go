package proto

import "framewire/internal/wireio"

type ExecuteMessage struct {
	Portal  string
	MaxRows uint32
}

func (m *ExecuteMessage) payloadLen() int {
	return len(m.Portal) + 1 + 4
}

func (m *ExecuteMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *ExecuteMessage) Encode(dst []byte) ([]byte, error) {
	dst, err := finishHeader(dst, msgTypeExecute, m.payloadLen())
	if err != nil {
		return nil, err
	}
	dst = append(dst, m.Portal...)
	dst = append(dst, 0)
	dst = wireio.AppendUint32(dst, m.MaxRows)
	return dst, nil
}
