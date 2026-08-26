package hash

import "testing"

func TestHexSHA256Stable(t *testing.T) {
	a := HexSHA256([]byte("workflow-runtime"))
	b := HexSHA256([]byte("workflow-runtime"))
	if a != b || len(a) != 64 {
		t.Fatalf("unstable or wrong length: %q", a)
	}
}

func TestTruncate(t *testing.T) {
	d := HexSHA256([]byte("x"))
	if Truncate(d, 8) != d[:8] {
		t.Fatal("truncate mismatch")
	}
}
