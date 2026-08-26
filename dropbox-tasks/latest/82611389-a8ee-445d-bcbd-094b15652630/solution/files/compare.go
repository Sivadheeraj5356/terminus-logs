package semver

import (
	"strconv"
	"strings"
)

func GTE(version, minimum string) bool {
	return compare(version, minimum) >= 0
}

func compare(a, b string) int {
	av := parseParts(a)
	bv := parseParts(b)
	for i := 0; i < 3; i++ {
		if av[i] > bv[i] {
			return 1
		}
		if av[i] < bv[i] {
			return -1
		}
	}
	return 0
}

func parseParts(v string) [3]int {
	parts := strings.Split(v, ".")
	out := [3]int{}
	for i := 0; i < 3; i++ {
		if i >= len(parts) {
			break
		}
		n, err := strconv.Atoi(strings.TrimSpace(parts[i]))
		if err != nil {
			continue
		}
		out[i] = n
	}
	return out
}
