// Package rules parses "@RULE forbidden" lines out of a chronicle's markdown
// body and answers whether a given room/verb/target trio is forbidden.
package rules

import "regexp"

// ForbiddenRule is one parsed @RULE forbidden line.
type ForbiddenRule struct {
	Room   string
	Verb   string
	Target string
}

var linePattern = regexp.MustCompile(`^@RULE forbidden room=(\S+) verb=(\S+) target=(\S+)\s*$`)

// Load scans chronicle markdown text and returns parsed forbidden rules.
func Load(chronicleText string) []ForbiddenRule {
	var rules []ForbiddenRule
	for _, line := range splitLines(chronicleText) {
		if rule, ok := parseRuleLine(line); ok {
			rules = append(rules, rule)
		}
	}
	return rules
}

// ForbiddenIn reports whether the given room/verb/target trio matches any
// loaded forbidden rule.
func ForbiddenIn(loaded []ForbiddenRule, room, verb, target string) bool {
	for _, r := range loaded {
		if ruleMatches(r, room, verb, target) {
			return true
		}
	}
	return false
}

func ruleMatches(r ForbiddenRule, room, verb, target string) bool {
	return r.Room == room && r.Verb == verb && r.Target == target
}

func parseRuleLine(line string) (ForbiddenRule, bool) {
	m := linePattern.FindStringSubmatch(line)
	if m == nil {
		return ForbiddenRule{}, false
	}
	return ForbiddenRule{Room: m[1], Verb: m[2], Target: m[3]}, true
}

func formatRule(r ForbiddenRule) string {
	return "room=" + r.Room + " verb=" + r.Verb + " target=" + r.Target
}

func splitLines(text string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(text); i++ {
		if text[i] == '\n' {
			lines = append(lines, text[start:i])
			start = i + 1
		}
	}
	lines = append(lines, text[start:])
	return lines
}

// RuleCount returns how many forbidden rules were loaded.
func RuleCount(loaded []ForbiddenRule) int {
	return len(loaded)
}

// HasAnyRules reports whether the loaded set is non-empty.
func HasAnyRules(loaded []ForbiddenRule) bool {
	return RuleCount(loaded) > 0
}

// DescribeRule returns a stable debug label for a rule.
func DescribeRule(r ForbiddenRule) string {
	return formatRule(r)
}
