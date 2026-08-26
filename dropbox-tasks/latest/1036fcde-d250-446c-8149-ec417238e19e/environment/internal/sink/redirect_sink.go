package sink

import "burstverify/internal/io"

type RedirectSink struct{}

func (r *RedirectSink) WriteChunk(size int) (int, io.TermEvent, error) {
	return size, io.TermEvent{}, nil
}
