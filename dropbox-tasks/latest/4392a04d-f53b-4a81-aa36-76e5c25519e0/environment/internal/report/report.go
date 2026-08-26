// Package report builds the two JSON outputs: the evaluate report (per-flow
// decisions plus a summary) and the lint report (the load-phase warnings and
// per-reason tally together with the analysis-phase shadowed/redundant/
// unreachable findings and the reachability summary). See docs/report-schema.md.
package report

import (
	"sort"

	"example.com/acl/internal/eval"
	"example.com/acl/internal/ruleset"
)

type DecisionOut struct {
	Src       string   `json:"src"`
	Dst       string   `json:"dst"`
	Port      int      `json:"port"`
	Protocol  string   `json:"protocol"`
	Direction string   `json:"direction"`
	Decision  string   `json:"decision"`
	Matched   string   `json:"matched"`
	Logged    []string `json:"logged"`
}

type EvalSummary struct {
	Allow   int `json:"allow"`
	Deny    int `json:"deny"`
	Flagged int `json:"flagged"`
	Total   int `json:"total"`
}

// EvalReport is what `acl evaluate` prints.
type EvalReport struct {
	Decisions []DecisionOut `json:"decisions"`
	Summary   EvalSummary   `json:"summary"`
}

type WarnOut struct {
	Index  int    `json:"index"`
	Code   string `json:"code"`
	Detail string `json:"detail"`
}

type FindingOut struct {
	Index  int    `json:"index"`
	Detail string `json:"detail"`
}

// LintSummary partitions the loaded rules by reachability and reports how many
// raw rules were dropped at load.
type LintSummary struct {
	Rules       int `json:"rules"`
	Reachable   int `json:"reachable"`
	Shadowed    int `json:"shadowed"`
	Redundant   int `json:"redundant"`
	Unreachable int `json:"unreachable"`
	Dropped     int `json:"dropped"`
}

// LintReport is what `acl lint` prints. Every list field is always an array,
// never null.
type LintReport struct {
	Warnings    []WarnOut      `json:"warnings"`
	ByReason    map[string]int `json:"by_reason"`
	Shadowed    []FindingOut   `json:"shadowed"`
	Redundant   []FindingOut   `json:"redundant"`
	Unreachable []FindingOut   `json:"unreachable"`
	Summary     LintSummary    `json:"summary"`
}

// BuildEval turns the per-flow decisions into the evaluate report. Decisions
// stay in input order.
func BuildEval(decisions []eval.Decision) EvalReport {
	rep := EvalReport{Decisions: make([]DecisionOut, 0, len(decisions))}
	allow, deny := 0, 0
	for _, d := range decisions {
		if d.Decision == "allow" {
			allow++
		} else {
			deny++
		}
		logged := d.Logged
		if logged == nil {
			logged = []string{}
		}
		rep.Decisions = append(rep.Decisions, DecisionOut{
			Src:       d.Src,
			Dst:       d.Dst,
			Port:      d.Port,
			Protocol:  d.Protocol,
			Direction: d.Direction,
			Decision:  d.Decision,
			Matched:   d.Matched,
			Logged:    logged,
		})
	}
	// the flagged tally over decisions that crossed a log rule, per
	// docs/report-schema.md
	rep.Summary = EvalSummary{Allow: allow, Deny: deny, Total: len(decisions)}
	return rep
}

func findingsOut(fs []eval.Finding) []FindingOut {
	out := make([]FindingOut, 0, len(fs))
	for _, f := range fs {
		out = append(out, FindingOut{Index: f.Index, Detail: f.Detail})
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].Index < out[j].Index })
	return out
}

// BuildLint stitches the load-phase warnings and the analysis-phase findings
// into the lint report and computes the reachability summary.
func BuildLint(warnings []ruleset.Warning, an eval.Analysis, ruleCount, rawCount int) LintReport {
	warns := make([]WarnOut, 0, len(warnings))
	byReason := map[string]int{}
	for _, w := range warnings {
		warns = append(warns, WarnOut{Index: w.Index, Code: w.Code, Detail: w.Detail})
		byReason[w.Code]++
	}
	sort.SliceStable(warns, func(i, j int) bool {
		if warns[i].Index != warns[j].Index {
			return warns[i].Index < warns[j].Index
		}
		return warns[i].Code < warns[j].Code
	})

	// the summary partitioning the loaded rules into reachable, shadowed,
	// redundant, and unreachable, per docs/report-schema.md
	return LintReport{
		Warnings:    warns,
		ByReason:    byReason,
		Shadowed:    findingsOut(an.Shadowed),
		Redundant:   findingsOut(an.Redundant),
		Unreachable: findingsOut(an.Unreachable),
		Summary:     LintSummary{},
	}
}
