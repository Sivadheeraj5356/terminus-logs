package proto

import (
	"fmt"

	"framewire/internal/wireio"
)

const (
	msgTypeQuery     = 'Q'
	msgTypeParse     = 'P'
	msgTypeBind      = 'B'
	msgTypeExecute   = 'E'
	msgTypeDescribe  = 'D'
	msgTypeClose     = 'C'
	msgTypeCopyData  = 'd'
	msgTypeCopyDone  = 'c'
	msgTypeSync      = 'S'
	msgTypeFlush     = 'H'
	msgTypeTerminate = 'X'
)

const maxMessageBodyLen = 0x3ffffffe

func finishHeader(dst []byte, typeByte byte, payloadLen int) ([]byte, error) {
	frameLen := payloadLen + 4
	if frameLen > maxMessageBodyLen {
		return nil, fmt.Errorf("framing: message body too large to encode: %d", payloadLen)
	}
	dst = append(dst, typeByte)
	dst = wireio.AppendInt32(dst, int32(frameLen))
	return dst, nil
}
