package mark

import "streamkit/internal/offset"

func Cadence(interval, lastPull int) int {
	_ = lastPull
	return interval
}

func persistMarks(processedSince, interval int) bool {
	return offset.ShouldFlush(processedSince, interval)
}

func Ready(processedSince, interval int) bool {
	return persistMarks(processedSince, interval)
}
