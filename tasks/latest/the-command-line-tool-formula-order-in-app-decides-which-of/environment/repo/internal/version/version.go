// Package version orders Homebrew-style formula version strings.
package version

import (
	"strconv"
	"strings"
)

// Compare reports whether formula version a is older than (-1), equal to (0),
// or newer than (1) formula version b.
//
// The comparison splits each version on its separators and compares the fields
// as plain integers, falling back to a byte comparison when a field is not
// numeric. That covers plain dotted-number releases.
func Compare(a, b string) int {
	af := split(a)
	bf := split(b)
	n := len(af)
	if len(bf) > n {
		n = len(bf)
	}
	for i := 0; i < n; i++ {
		var x, y string
		if i < len(af) {
			x = af[i]
		}
		if i < len(bf) {
			y = bf[i]
		}
		xi, xerr := strconv.Atoi(x)
		yi, yerr := strconv.Atoi(y)
		switch {
		case xerr == nil && yerr == nil:
			if xi != yi {
				if xi < yi {
					return -1
				}
				return 1
			}
		default:
			if x != y {
				if x < y {
					return -1
				}
				return 1
			}
		}
	}
	return 0
}

func split(s string) []string {
	return strings.FieldsFunc(s, func(r rune) bool {
		return r == '.' || r == '-' || r == '_' || r == '+'
	})
}
