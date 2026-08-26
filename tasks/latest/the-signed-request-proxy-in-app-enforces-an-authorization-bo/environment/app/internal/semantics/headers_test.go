package semantics

import "testing"

func TestJoinableListHeaders(t *testing.T) {
	policy := DefaultCurrentPolicy()
	headers := map[string][]string{
		"Accept": {"text/plain", " application/json"},
	}
	order := []string{"Accept"}
	got, err := ApplyHeaderPolicy(policy, headers, order)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Value != "text/plain, application/json" {
		t.Fatalf("unexpected join: %+v", got)
	}
}

func TestDuplicateSingletonRejected(t *testing.T) {
	policy := DefaultCurrentPolicy()
	headers := map[string][]string{
		"Host": {"a.example", "b.example"},
	}
	order := []string{"Host"}
	_, err := ApplyHeaderPolicy(policy, headers, order)
	if err == nil {
		t.Fatal("expected duplicate singleton error")
	}
}
