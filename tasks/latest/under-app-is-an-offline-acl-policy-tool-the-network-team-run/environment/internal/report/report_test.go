package report

import (
	"testing"

	"example.com/acl/internal/eval"
	"example.com/acl/internal/ruleset"
)

func TestBuildEvalCounts(t *testing.T) {
	decisions := []eval.Decision{
		{Decision: "allow", Matched: "r0", Logged: []string{}},
		{Decision: "deny", Matched: "default-deny", Logged: []string{}},
		{Decision: "allow", Matched: "r2", Logged: []string{"log0"}},
	}
	rep := BuildEval(decisions)
	if rep.Summary.Allow != 2 || rep.Summary.Deny != 1 || rep.Summary.Total != 3 {
		t.Errorf("summary counts wrong: %+v", rep.Summary)
	}
	if rep.Decisions == nil {
		t.Error("decisions must be an array, not nil")
	}
	for _, d := range rep.Decisions {
		if d.Logged == nil {
			t.Error("logged must be an array, not nil")
		}
	}
}

func TestBuildLintWiresWarnings(t *testing.T) {
	warns := []ruleset.Warning{
		{Index: 2, Code: "bad_cidr", Detail: "300.0.0.0/8"},
		{Index: 4, Code: "bad_port", Detail: "90-80"},
	}
	rep := BuildLint(warns, eval.Analysis{}, 3, 5)
	if len(rep.Warnings) != 2 {
		t.Fatalf("warnings not wired: %+v", rep.Warnings)
	}
	if rep.ByReason["bad_cidr"] != 1 || rep.ByReason["bad_port"] != 1 {
		t.Errorf("by_reason not tallied: %+v", rep.ByReason)
	}
	if rep.Shadowed == nil || rep.Redundant == nil || rep.Unreachable == nil {
		t.Error("finding arrays must be present, not nil")
	}
}
