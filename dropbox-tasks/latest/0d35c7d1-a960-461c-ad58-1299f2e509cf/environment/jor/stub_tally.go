package jor

import "qxhub/fyn"

// EchoTokens echoes matcher tokens for diagnostics; it does not assign keys.
func EchoTokens(rows []fyn.LaneRow) []string {
	out := make([]string, 0, len(rows))
	for _, r := range rows {
		for _, m := range r.Match {
			if m != "" {
				out = append(out, m)
			}
		}
	}
	return out
}
