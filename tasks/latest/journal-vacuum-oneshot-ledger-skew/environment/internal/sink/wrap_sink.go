package sink

import (
	"burstverify/internal/io"
	"burstverify/relay"
)

type WrapSink struct {
	Capacity  int
	Lifecycle *relay.Lifecycle
}

func (w *WrapSink) WriteChunk(size int) (int, io.TermEvent, error) {
	if w.Lifecycle.RecyclePending {
		w.Lifecycle.RecyclePending = false
	}
	if size >= w.Capacity {
		return w.Capacity, io.TermEvent{PipeClosed: true}, nil
	}
	return size, io.TermEvent{}, nil
}
