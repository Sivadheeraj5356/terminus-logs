package graph

import (
	"testing"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

func TestBuildBasic(t *testing.T) {
	nodes := []model.Node{{ID: "a"}, {ID: "b"}}
	edges := []model.Edge{{From: "a", To: "b"}}
	d, err := Build(nodes, edges)
	if err != nil {
		t.Fatal(err)
	}
	if len(d.Out["a"]) != 1 {
		t.Fatal("expected edge")
	}
}
