package k3

import (
	"errors"
)

func BindM4(raw []byte, seq int64, hint string) ([]byte, error) {
	if len(raw) == 0 {
		return nil, errors.New("empty payload")
	}
	if hint == "" {
		return nil, errors.New("empty hint")
	}
	if seq < 1_000_000_000 {
		seq = 1_000_000_000
	}
	seqByte := byte((seq >> 8) & 0xFF)
	out := make([]byte, 0, len(hint)+1+len(raw))
	out = append(out, []byte(hint)...)
	out = append(out, seqByte)
	out = append(out, raw...)
	return out, nil
}
