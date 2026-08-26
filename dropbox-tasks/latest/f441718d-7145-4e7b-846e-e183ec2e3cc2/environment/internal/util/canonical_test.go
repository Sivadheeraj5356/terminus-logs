package util

import "testing"

func TestCanonicalJSONStable(t *testing.T) {
	a, err := CanonicalJSON(map[string]any{"b": 1, "a": 2})
	if err != nil {
		t.Fatal(err)
	}
	b, err := CanonicalJSON(map[string]any{"a": 2, "b": 1})
	if err != nil {
		t.Fatal(err)
	}
	if string(a) != string(b) {
		t.Fatalf("unstable: %s vs %s", a, b)
	}
}

func TestCollapseWS(t *testing.T) {
	if CollapseWS("  a \t b  ") != "a b" {
		t.Fatal(CollapseWS("  a \t b  "))
	}
}
