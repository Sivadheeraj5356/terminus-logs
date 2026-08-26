// Package cidr does IPv4 parsing and containment with plain uint32 math, no
// net package. The contract is in docs/cidr-math.md.
package cidr

import (
	"fmt"
	"strconv"
	"strings"
)

// ParseIP packs "192.168.1.10" into a uint32, first octet in the high byte.
// Strict: exactly four octets, each 0..255, no whitespace, no shorthand.
func ParseIP(s string) (uint32, bool) {
	parts := strings.Split(s, ".")
	if len(parts) != 4 {
		return 0, false
	}
	var ip uint32
	for _, p := range parts {
		if p == "" || len(p) > 3 {
			return 0, false
		}
		n, err := strconv.Atoi(p)
		if err != nil || n < 0 || n > 255 {
			return 0, false
		}
		ip = ip<<8 | uint32(n)
	}
	return ip, true
}

// FormatIP renders a packed address back to dotted-quad.
func FormatIP(ip uint32) string {
	return fmt.Sprintf("%d.%d.%d.%d", byte(ip>>24), byte(ip>>16), byte(ip>>8), byte(ip))
}

// Net is a parsed A.B.C.D/P block. Base is stored exactly as parsed; call
// Canonical to snap it to the subnet boundary.
type Net struct {
	Base   uint32
	Prefix int // 0..32
}

// ParseCIDR parses "A.B.C.D/P" and keeps the base exactly as written; the
// loader decides whether to canonicalize. Anything malformed is an error so the
// loader can record a bad_cidr.
func ParseCIDR(s string) (Net, error) {
	slash := strings.IndexByte(s, '/')
	if slash < 0 {
		return Net{}, fmt.Errorf("missing prefix")
	}
	ip, ok := ParseIP(s[:slash])
	if !ok {
		return Net{}, fmt.Errorf("bad address %q", s[:slash])
	}
	prefix, err := strconv.Atoi(s[slash+1:])
	if err != nil {
		return Net{}, fmt.Errorf("bad prefix %q", s[slash+1:])
	}
	if prefix < 0 || prefix > 32 {
		return Net{}, fmt.Errorf("prefix out of range: %d", prefix)
	}
	return Net{Base: ip, Prefix: prefix}, nil
}

// Mask gives the network mask for a prefix: top `prefix` bits set, rest clear.
// /0 is all zeros (matches everything), /32 is all ones. The host-bit count is
// 32-prefix; see docs/cidr-math.md for the shift amount.
func Mask(prefix int) uint32 {
	if prefix <= 0 {
		return 0
	}
	return ^uint32(0) << (32 - prefix)
}

// Canonical returns the block with its host bits cleared, so an unaligned base
// is snapped down to the true network number.
func (n Net) Canonical() Net {
	return Net{Base: n.Base & Mask(n.Prefix), Prefix: n.Prefix}
}

// IsCanonical reports whether the base already has its host bits clear.
func (n Net) IsCanonical() bool {
	return n.Base == n.Base&Mask(n.Prefix)
}

// String renders the block as base/prefix using the stored base.
func (n Net) String() string {
	return FormatIP(n.Base) + "/" + strconv.Itoa(n.Prefix)
}

// Contains masks both sides, so a base that isn't on a boundary still compares
// right.
func (n Net) Contains(ip uint32) bool {
	m := Mask(n.Prefix)
	return (ip & m) == (n.Base & m)
}

// Covers is true when n is a superset of other: n's prefix is no bigger than
// other's and other's base lands inside n.
func (n Net) Covers(other Net) bool {
	if n.Prefix > other.Prefix {
		return false
	}
	return n.Contains(other.Base)
}
