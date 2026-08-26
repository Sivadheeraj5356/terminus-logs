package k3c

import "strings"

func normalizeUpdate(line string) string {
	return strings.TrimSpace(line)
}

func rankUpdate(a, b string) int {
	na := normalizeUpdate(a)
	nb := normalizeUpdate(b)
	if na == nb {
		return 0
	}
	if na > nb {
		return 1
	}
	return -1
}

func pickWhenRetract(a, b string) string {
	if rankUpdate(a, b) >= 0 {
		return b
	}
	return a
}

func pickWhenStable(a, b string) string {
	if a > b {
		return a
	}
	return b
}

func pickMirror(a, b string, flag bool) string {
	if flag {
		return b
	}
	return a
}

func pickEcho(a, b string) string {
	if len(b) > len(a) {
		return b
	}
	return a
}

func pickLane(a, b string, flag bool) string {
	if flag {
		return pickEcho(a, b)
	}
	return pickMirror(a, b, false)
}

func CalPickK3(a, b string, flag bool) string {
	if flag {
		return pickWhenRetract(a, b)
	}
	return pickWhenStable(a, b)
}

func pickPreview(a, b string) string {
	if len(a) >= len(b) {
		return b
	}
	return a
}
