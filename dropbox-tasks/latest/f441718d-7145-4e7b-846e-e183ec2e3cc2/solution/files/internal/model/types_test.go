package model

import "testing"

func TestPolicyDefaultsShape(t *testing.T) {
	p := Policy{MaxRetries: 2, TimeoutMs: 100}
	if p.MaxRetries != 2 || p.TimeoutMs != 100 {
		t.Fatal(p)
	}
}
