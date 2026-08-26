package semantics

import "testing"

func TestNormalizeCurrentPath(t *testing.T) {
	p := &Profile{UppercasePercent: true, RemoveDotSegments: true}
	path, _, canonical, _, err := NormalizeTarget(p, "/foo/%62ar/../baz")
	if err != nil {
		t.Fatal(err)
	}
	if path != "/foo/baz" {
		t.Fatalf("path=%q", path)
	}
	if canonical != "/foo/baz" {
		t.Fatalf("canonical=%q", canonical)
	}
}

func TestLegacyQueryPreserved(t *testing.T) {
	p := &Profile{PreserveLegacyQuery: true}
	_, query, _, pairs, err := NormalizeTarget(p, "/x?b=2&a=1")
	if err != nil {
		t.Fatal(err)
	}
	if query != "b=2&a=1" {
		t.Fatalf("query=%q", query)
	}
	if len(pairs) != 2 || pairs[0].Key != "b" {
		t.Fatalf("pairs=%+v", pairs)
	}
}
