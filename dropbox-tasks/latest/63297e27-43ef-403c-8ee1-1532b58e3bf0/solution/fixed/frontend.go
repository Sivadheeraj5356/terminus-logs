package proto

import (
	"fmt"
	"io"
)

type Frontend struct {
	w   io.Writer
	buf []byte
}

func NewFrontend(w io.Writer) *Frontend {
	return &Frontend{w: w}
}

func (f *Frontend) Send(msg FrontendMessage) error {
	buf, err := msg.Encode(f.buf[:0])
	if err != nil {
		return fmt.Errorf("send: refusing to transmit unframeable message: %w", err)
	}
	f.buf = buf
	_, err = f.w.Write(buf)
	return err
}

func (f *Frontend) SendStartup(msg *StartupMessage) error {
	buf, err := msg.Encode(f.buf[:0])
	if err != nil {
		return err
	}
	f.buf = buf
	_, err = f.w.Write(buf)
	return err
}
