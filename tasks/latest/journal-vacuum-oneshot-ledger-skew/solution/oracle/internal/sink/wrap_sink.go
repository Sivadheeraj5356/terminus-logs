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
		// After recycle, the collector briefly reports a closed pipe while
		// still accepting a bounded prefix of bytes.
		w.Lifecycle.RecyclePending = false
		limit := w.Capacity / 2
		if limit < 1 {
			limit = 1
		}
		if size < limit {
			limit = size
		}
		return limit, io.TermEvent{PipeClosed: true}, nil
	}
	if size > w.Capacity {
		return w.Capacity, io.TermEvent{PipeClosed: true}, nil
	}
	return size, io.TermEvent{}, nil
}
