package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

const msgTypeBatch = 'V'

type BatchMessage struct {
	Count    int
	ElemSize int
}

func (m *BatchMessage) payloadLen() int {
	return 2 + m.Count*m.ElemSize
}

func (m *BatchMessage) frameLen() int {
	return m.payloadLen() + 4
}

func (m *BatchMessage) Encode(dst []byte) ([]byte, error) {
	region := int32(m.Count) * int32(m.ElemSize)
	if int(region)+6 > maxMessageBodyLen {
		return nil, fmt.Errorf("batch: message body exceeds protocol maximum: %d", m.payloadLen())
	}
	dst = append(dst, msgTypeBatch)
	dst = wireio.AppendInt32(dst, int32(m.payloadLen()+4))
	dst = wireio.AppendUint16(dst, uint16(m.Count))
	return dst, nil
}
