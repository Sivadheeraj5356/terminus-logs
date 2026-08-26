package engine

import (
	"testing"

	"lab.local/salt_pond/pkg/pond"
)

func TestReplayEmpty(t *testing.T) {
	out := Replay(pond.Plan{PondID: "empty", MinMastEpoch: 3}, nil, nil, nil)
	if out.FrontSum != 0 {
		t.Fatalf("unexpected front sum %d", out.FrontSum)
	}
}
