package semantics

import (
	"fmt"
	"net/url"
	"sort"
	"strings"
)

func ParseQueryLegacy(q string) []QueryPair {
	return parseLegacyQuery(q)
}

func ParseQueryCurrent(q string) ([]QueryPair, error) {
	return parseCurrentQuery(q)
}

func EncodeQueryCurrent(pairs []QueryPair) string {
	return encodeCurrentQuery(pairs)
}

func SortQueryPairs(pairs []QueryPair) []QueryPair {
	out := append([]QueryPair(nil), pairs...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Key != out[j].Key {
			return out[i].Key < out[j].Key
		}
		return out[i].Value < out[j].Value
	})
	return out
}

func ValidateQueryPair(key, value string) error {
	if key == "" {
		return fmt.Errorf("empty query key")
	}
	if strings.ContainsAny(key, " \t\r\n") {
		return fmt.Errorf("invalid query key whitespace")
	}
	if strings.ContainsAny(value, "\r\n") {
		return fmt.Errorf("invalid query value")
	}
	return nil
}

func UnescapeQueryComponent(s string) (string, error) {
	return url.QueryUnescape(s)
}
