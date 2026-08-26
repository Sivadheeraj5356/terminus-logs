package cidr

import "testing"

func TestParseIP(t *testing.T) {
	cases := []struct {
		in   string
		want uint32
		ok   bool
	}{
		{"0.0.0.0", 0, true},
		{"255.255.255.255", 0xFFFFFFFF, true},
		{"192.168.1.10", 0xC0A8010A, true},
		{"10.0.0.1", 0x0A000001, true},
		{"256.0.0.1", 0, false},
		{"1.2.3", 0, false},
		{"1.2.3.4.5", 0, false},
		{"1.2.3.a", 0, false},
		{" 1.2.3.4", 0, false},
	}
	for _, c := range cases {
		got, ok := ParseIP(c.in)
		if ok != c.ok || (ok && got != c.want) {
			t.Errorf("ParseIP(%q) = %#x,%v want %#x,%v", c.in, got, ok, c.want, c.ok)
		}
	}
}

func TestParseCIDRErrors(t *testing.T) {
	for _, s := range []string{"10.0.0.0", "10.0.0.0/33", "10.0.0.0/-1", "300.0.0.0/8", "10.0.0.0/x"} {
		if _, err := ParseCIDR(s); err == nil {
			t.Errorf("ParseCIDR(%q) should have failed", s)
		}
	}
}

func TestParseCIDROK(t *testing.T) {
	n, err := ParseCIDR("192.168.1.10/24")
	if err != nil {
		t.Fatalf("ParseCIDR: %v", err)
	}
	if n.Prefix != 24 {
		t.Errorf("prefix = %d, want 24", n.Prefix)
	}
}
