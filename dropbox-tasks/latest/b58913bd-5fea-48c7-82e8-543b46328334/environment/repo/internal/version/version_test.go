package version

import (
	"reflect"
	"testing"
)

// These cover the plain dotted-number releases the catalog started with. The
// decorated-version behaviour (pre-releases, patch levels, letters, ...) is
// exercised by the wider catalog acceptance suite, not here.
func TestCompareNumeric(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{
		{"1.0", "1.1", -1},
		{"1.1", "1.0", 1},
		{"2.0", "2.0", 0},
		{"1.10", "1.9", 1},
		{"1.2.3", "1.2.3", 0},
		{"0.9", "1.0", -1},
	}
	for _, c := range cases {
		if got := Compare(c.a, c.b); got != c.want {
			t.Errorf("Compare(%q, %q) = %d, want %d", c.a, c.b, got, c.want)
		}
	}
}

func TestSortNumeric(t *testing.T) {
	got := []string{"1.10", "0.9", "1.2"}
	Sort(got)
	want := []string{"0.9", "1.2", "1.10"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("Sort = %v, want %v", got, want)
	}
}

func TestNewestNumeric(t *testing.T) {
	if got := Newest([]string{"1.2", "1.10", "0.9"}); got != "1.10" {
		t.Errorf("Newest = %q, want %q", got, "1.10")
	}
	if got := Newest(nil); got != "" {
		t.Errorf("Newest(nil) = %q, want empty", got)
	}
}
