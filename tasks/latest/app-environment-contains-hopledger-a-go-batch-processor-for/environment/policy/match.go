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
	for _, rule := range doc.Rules {
		prefix := strings.TrimSuffix(rule.Pattern, "*")
		if strings.HasPrefix(linkID, prefix) {
			return rule.SLAMs
		}
	}
	return doc.DefaultSLAMs
}
