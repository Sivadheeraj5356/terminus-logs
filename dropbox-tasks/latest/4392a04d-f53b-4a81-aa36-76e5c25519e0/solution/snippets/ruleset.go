// Package ruleset loads an ordered ACL ruleset from JSON and validates each
// rule on its own: id, action, src/dst CIDR, port range, protocol, direction,
// priority. A rule that trips any check is dropped but keeps its original file
// index so diagnostics still point at it. Valid blocks are canonicalized (host
// bits masked off); a block that had to be snapped emits an informational
// normalized note and the rule still loads. See docs/ruleset-format.md.
package ruleset

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"

	"example.com/acl/internal/cidr"
)

type rawRule struct {
	ID        string `json:"id"`
	Action    string `json:"action"`
	Src       string `json:"src"`
	Dst       string `json:"dst"`
	PortMin   int    `json:"port_min"`
	PortMax   int    `json:"port_max"`
	Protocol  string `json:"protocol"`
	Direction string `json:"direction"`
	Priority  int    `json:"priority"`
}

// Rule is a validated ACL rule. Index is its 0-based file position and survives
// even when earlier rules get dropped. Src and Dst are canonical.
type Rule struct {
	Index     int
	ID        string
	Action    string // "allow", "deny", or "log"
	Src       cidr.Net
	Dst       cidr.Net
	PortMin   int
	PortMax   int
	Protocol  string // "tcp", "udp", "icmp", or "any"
	Direction string // "inbound", "outbound", or "any"
	Priority  int
}

// Warning is a rule-level note from the load phase. Index points at the
// offending rule, Code is the reason, Detail is context.
type Warning struct {
	Index  int
	Code   string
	Detail string
}

type Loaded struct {
	Rules    []Rule    // passed validation, in file order
	Warnings []Warning // load-phase notes
	RawCount int       // number of rule objects in the file, including dropped ones
}

func validProtocol(p string) bool {
	return p == "tcp" || p == "udp" || p == "icmp" || p == "any"
}

func validAction(a string) bool {
	return a == "allow" || a == "deny" || a == "log"
}

func validDirection(d string) bool {
	return d == "inbound" || d == "outbound" || d == "any"
}

// Load reads and validates the ruleset at path. See docs/ruleset-format.md for
// the reason codes.
func Load(path string) (Loaded, error) {
	blob, err := os.ReadFile(path)
	if err != nil {
		return Loaded{}, err
	}
	var raw []rawRule
	if err := json.Unmarshal(blob, &raw); err != nil {
		return Loaded{}, fmt.Errorf("parse ruleset: %w", err)
	}

	loaded := Loaded{RawCount: len(raw)}
	seen := map[string]bool{}

	for i, rr := range raw {
		dropped := false
		warn := func(code, detail string) {
			loaded.Warnings = append(loaded.Warnings, Warning{Index: i, Code: code, Detail: detail})
			dropped = true
		}

		// id: non-empty and first-come claims it.
		if rr.ID == "" {
			warn("bad_id", "(empty)")
		} else if seen[rr.ID] {
			warn("dup_id", rr.ID)
		} else {
			seen[rr.ID] = true
		}

		if !validAction(rr.Action) {
			warn("bad_action", rr.Action)
		}
		if !validProtocol(rr.Protocol) {
			warn("bad_proto", rr.Protocol)
		}
		if !validDirection(rr.Direction) {
			warn("bad_direction", rr.Direction)
		}

		srcNet, serr := cidr.ParseCIDR(rr.Src)
		if serr != nil {
			warn("bad_cidr", rr.Src)
		}
		dstNet, derr := cidr.ParseCIDR(rr.Dst)
		if derr != nil {
			warn("bad_cidr", rr.Dst)
		}

		if rr.PortMin < 0 || rr.PortMax > 65535 || rr.PortMin > rr.PortMax {
			warn("bad_port", fmt.Sprintf("%d-%d", rr.PortMin, rr.PortMax))
		}
		if rr.Priority < 0 || rr.Priority > 1000 {
			warn("bad_priority", strconv.Itoa(rr.Priority))
		}

		if dropped {
			continue
		}

		// Canonicalize; note any block that had to be snapped.
		if !srcNet.IsCanonical() {
			loaded.Warnings = append(loaded.Warnings, Warning{
				Index: i, Code: "normalized", Detail: srcNet.Canonical().String(),
			})
		}
		if !dstNet.IsCanonical() {
			loaded.Warnings = append(loaded.Warnings, Warning{
				Index: i, Code: "normalized", Detail: dstNet.Canonical().String(),
			})
		}

		loaded.Rules = append(loaded.Rules, Rule{
			Index:     i,
			ID:        rr.ID,
			Action:    rr.Action,
			Src:       srcNet.Canonical(),
			Dst:       dstNet.Canonical(),
			PortMin:   rr.PortMin,
			PortMax:   rr.PortMax,
			Protocol:  rr.Protocol,
			Direction: rr.Direction,
			Priority:  rr.Priority,
		})
	}
	return loaded, nil
}
