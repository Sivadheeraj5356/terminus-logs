package proto

type DescribeMessage struct {
	ObjectType byte
	Name       string
}

func (m *DescribeMessage) payloadLen() int {
	return 1 + len(m.Name) + 1
}

func (m *DescribeMessage) Encode(dst []byte) ([]byte, error) {
	dst, err := finishHeader(dst, msgTypeDescribe, m.payloadLen())
	if err != nil {
		return nil, err
	}
	dst = append(dst, m.ObjectType)
	dst = append(dst, m.Name...)
	dst = append(dst, 0)
	return dst, nil
}
