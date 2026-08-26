package proto

import (
	"errors"
	"io"

	"framewire/internal/wireio"
)

type RawMessage struct {
	Type byte
	Body []byte
}

func ReadMessage(r io.Reader) (*RawMessage, error) {
	header := make([]byte, 5)
	if _, err := io.ReadFull(r, header); err != nil {
		return nil, err
	}
	frameLen := int(int32(wireio.Uint32(header[1:5])))
	if frameLen < 4 {
		return nil, errors.New("backend: invalid message length")
	}
	body := make([]byte, frameLen-4)
	if _, err := io.ReadFull(r, body); err != nil {
		return nil, err
	}
	return &RawMessage{Type: header[0], Body: body}, nil
}

func ReadAll(r io.Reader) ([]*RawMessage, error) {
	var out []*RawMessage
	for {
		m, err := ReadMessage(r)
		if errors.Is(err, io.EOF) {
			return out, nil
		}
		if err != nil {
			return out, err
		}
		out = append(out, m)
	}
}
