package dag

import (
	"testing"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

func TestLineageParentsEmpty(t *testing.T) {
	plan := &model.ExecutionPlan{Edges: []model.Edge{{From: "a", To: "b"}}}
	if got := LineageParents(plan, "a"); len(got) != 0 {
		t.Fatalf("expected no parents: %v", got)
	}
	if got := LineageParents(plan, "b"); len(got) != 1 || got[0] != "a" {
		t.Fatalf("unexpected parents: %v", got)
	}
}
