package io

type TermEvent struct {
	PipeClosed bool
}

type Writer interface {
	WriteChunk(size int) (int, TermEvent, error)
}
