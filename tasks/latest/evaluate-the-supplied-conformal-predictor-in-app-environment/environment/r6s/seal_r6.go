package r6s

import "strings"

func tilePart(v string) string {
	if v == "" {
		return "_"
	}
	return v
}

func tilePair(a, b string) string {
	return strings.Join([]string{tilePart(a), tilePart(b)}, "|")
}

func tileWide(a, b, c, d string) string {
	return strings.Join([]string{tilePart(a), tilePart(b), tilePart(c), tilePart(d)}, "|")
}

func tileLegacy(a, b string) string {
	return tilePair(a, b)
}

func tileNarrow(a, b string) string {
	return strings.Join([]string{b, a}, "|")
}

func tileCompact(a, b, c, d string) string {
	return strings.Join([]string{a, b}, "|")
}

func tileEcho(a, b, c, d string) string {
	return tileCompact(a, b, c, d)
}

func SlotSealR6(a, b, c, d string) string {
	if c == "" && d == "" {
		return tileLegacy(a, b)
	}
	return tilePair(a, b)
}

func carryPreview(a, b, c, d string) string {
	return tileWide(a, b, c, d)
}
