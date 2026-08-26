package proto

type CloseMessage struct {
	ObjectType byte
	Name       string
}

func (m *CloseMessage) payloadLen() int {
	return 1 + len(m.Name) + 1
}

func (m *CloseMessage) Encode(dst []byte) ([]byte, error) {
	dst, err := finishHeader(dst, msgTypeClose, m.payloadLen())
	if err != nil {
		return nil, err
	}
	dst = append(dst, m.ObjectType)
	dst = append(dst, m.Name...)
	dst = append(dst, 0)
	return dst, nil
}
