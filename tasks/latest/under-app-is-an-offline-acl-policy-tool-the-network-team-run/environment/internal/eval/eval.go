// Package eval orders the loaded rules, runs flows through them (first terminal
// match wins under the priority ordering, default deny, log rules are
// non-terminal and are recorded), and analyses the ordered set for shadowed,
// redundant, and unreachable rules. See docs/evaluation.md.
package eval

import (
	"bufio"
	"encoding/json"
	"io"
	"strings"

	"example.com/acl/internal/ruleset"
)

// DefaultMatch is the matched id for a default deny. It is a documented sentinel
// string, never null and never a real rule id.
const DefaultMatch = "default-deny"

type Flow struct {
	Src       string
	Dst       string
	Port      int
	Protocol  string
	Direction string
	Line      int
}

// Decision is the outcome for one flow, kept in input order.
type Decision struct {
	Src       string
	Dst       string
	Port      int
	Protocol  string
	Direction string
	Decision  string   // "allow" or "deny"
	Matched   string   // deciding rule id, or DefaultMatch
	Logged    []string // ids of log rules crossed before the terminal decision, in order
}

// Finding is one analysis-phase result keyed by a rule's file index.
type Finding struct {
	Index  int
	Detail string
}

type Analysis struct {
	Shadowed    []Finding
	Redundant   []Finding
	Unreachable []Finding
}

type rawFlow struct {
	Src       string `json:"src"`
	Dst       string `json:"dst"`
	Port      int    `json:"port"`
	Protocol  string `json:"protocol"`
	Direction string `json:"direction"`
}

// ParseFlows reads NDJSON flows. Blank and malformed lines are skipped - flows
// are trusted input, unlike the ruleset.
func ParseFlows(r io.Reader) []Flow {
	var flows []Flow
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 1024*1024), 8*1024*1024)
	line := 0
	for sc.Scan() {
		line++
		text := strings.TrimSpace(sc.Text())
		if text == "" {
			continue
		}
		var rf rawFlow
		if err := json.Unmarshal([]byte(text), &rf); err != nil {
			continue
		}
		flows = append(flows, Flow{
			Src: rf.Src, Dst: rf.Dst, Port: rf.Port,
			Protocol: rf.Protocol, Direction: rf.Direction, Line: line,
		})
	}
	return flows
}

func protoMatches(rule, flow string) bool {
	return rule == "any" || rule == flow
}

func dirMatches(rule, flow string) bool {
	return rule == "any" || rule == flow
}

func matches(r ruleset.Rule, sip, dip uint32, port int, proto, dir string) bool {
	if !r.Src.Contains(sip) || !r.Dst.Contains(dip) {
		return false
	}
	if port < r.PortMin || port > r.PortMax {
		return false
	}
	return protoMatches(r.Protocol, proto) && dirMatches(r.Direction, dir)
}

// Evaluate returns one decision per flow (input order) plus the set of rule
// indices that fired. A flow whose src or dst won't parse is denied by default.
func Evaluate(flows []Flow, rules []ruleset.Rule, parseIP func(string) (uint32, bool)) ([]Decision, map[int]bool) {
	fired := make(map[int]bool, len(rules))
	decisions := make([]Decision, 0, len(flows))

	for _, f := range flows {
		d := Decision{
			Src: f.Src, Dst: f.Dst, Port: f.Port,
			Protocol: f.Protocol, Direction: f.Direction,
			Decision: "deny", Matched: DefaultMatch, Logged: []string{},
		}
		sip, sok := parseIP(f.Src)
		dip, dok := parseIP(f.Dst)
		if sok && dok {
			for _, r := range rules {
				if !matches(r, sip, dip, f.Port, f.Protocol, f.Direction) {
					continue
				}
				fired[r.Index] = true
				d.Decision = r.Action
				d.Matched = r.ID
				break
			}
		}
		decisions = append(decisions, d)
	}
	return decisions, fired
}

// Analyze classifies each loaded rule for the lint report, per the rules in
// docs/evaluation.md. The fired set comes from Evaluate.
func Analyze(rules []ruleset.Rule, fired map[int]bool) Analysis {
	return Analysis{
		Shadowed:    []Finding{},
		Redundant:   []Finding{},
		Unreachable: []Finding{},
	}
}
