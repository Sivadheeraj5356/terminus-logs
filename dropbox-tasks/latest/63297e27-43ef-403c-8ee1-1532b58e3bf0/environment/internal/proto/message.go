package proto

type FrontendMessage interface {
	Encode(dst []byte) ([]byte, error)
}

type frameSizer interface {
	frameLen() int
}

func IntendedFrameLen(msg FrontendMessage) int {
	if s, ok := msg.(frameSizer); ok {
		return s.frameLen()
	}
	return -1
}
