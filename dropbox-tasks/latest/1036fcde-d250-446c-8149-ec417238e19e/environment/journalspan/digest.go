package journalspan

import (
	"crypto/sha256"
	"fmt"
)

type ByteSpan struct {
	StartOffset   int `json:"start_offset"`
	EndOffset     int `json:"end_offset"`
	ObservedBytes int `json:"observed_bytes"`
}

func MixFingerprint(writerEpoch, readerEpoch string, span ByteSpan) string {
	payload := fmt.Sprintf(
		"%s|%s|%d|%d|%d",
		writerEpoch,
		readerEpoch,
		span.StartOffset,
		span.EndOffset,
		span.ObservedBytes,
	)
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum)[:32]
}
