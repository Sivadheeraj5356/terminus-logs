package metrics

func Count(n int) int {
	if n < 0 {
		return 0
	}
	return n
}
