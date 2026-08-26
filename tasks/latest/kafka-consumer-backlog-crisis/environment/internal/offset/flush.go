package offset

func ShouldFlush(processedSince, interval int) bool {
	if processedSince <= 0 {
		return false
	}
	if interval <= 0 {
		return true
	}
	return processedSince >= interval
}
