package policy

import "strings"

func patternTier(pattern string) int {
	switch {
	case pattern == "*>*":
		return 4
	case strings.HasPrefix(pattern, "*>"):
		return 3
	case strings.HasSuffix(pattern, ">*"):
		return 2
	default:
		return 1
	}
}

func matchPattern(pattern, linkID string) bool {
	if !strings.Contains(linkID, ">") {
		return false
	}
	parts := strings.SplitN(linkID, ">", 2)
	src, dst := parts[0], parts[1]
	switch {
	case pattern == "*>*":
		return true
	case strings.HasSuffix(pattern, ">*"):
		return src == pattern[:len(pattern)-2]
	case strings.HasPrefix(pattern, "*>"):
		return dst == pattern[2:]
	default:
		return linkID == pattern
	}
}

func SLA(doc *Document, linkID string) int {
	if doc == nil {
		return 0
	}
	bestTier := 999
	bestIdx := 999
	best := -1
	for idx, rule := range doc.Rules {
		if !matchPattern(rule.Pattern, linkID) {
			continue
		}
		tier := patternTier(rule.Pattern)
		if tier < bestTier || (tier == bestTier && idx < bestIdx) {
			bestTier = tier
			bestIdx = idx
			best = rule.SLAMs
		}
	}
	if best >= 0 {
		return best
	}
	return doc.DefaultSLAMs
}
