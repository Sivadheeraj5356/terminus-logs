package proto

type SyncMessage struct{}

func (m *SyncMessage) Encode(dst []byte) ([]byte, error) {
	return finishHeader(dst, msgTypeSync, 0)
}

type FlushMessage struct{}

func (m *FlushMessage) Encode(dst []byte) ([]byte, error) {
	return finishHeader(dst, msgTypeFlush, 0)
}

type TerminateMessage struct{}

func (m *TerminateMessage) Encode(dst []byte) ([]byte, error) {
	return finishHeader(dst, msgTypeTerminate, 0)
}

type CopyDoneMessage struct{}

func (m *CopyDoneMessage) Encode(dst []byte) ([]byte, error) {
	return finishHeader(dst, msgTypeCopyDone, 0)
}
