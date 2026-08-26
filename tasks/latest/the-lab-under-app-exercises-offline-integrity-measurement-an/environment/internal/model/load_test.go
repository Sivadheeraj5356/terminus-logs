package model

import "testing"

func TestLoadPolicy(t *testing.T) {
	p, raw, err := LoadPolicy("../../data/policy.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Tiers) != 4 {
		t.Fatalf("tiers: %d", len(p.Tiers))
	}
	if len(raw) < 11 {
		t.Fatalf("raw clauses: %d", len(raw))
	}
}
