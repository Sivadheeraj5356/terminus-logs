package dnszone

import (
	"fmt"
	"strings"

	"github.com/miekg/dns"
)

func CanonicalKey(r Record) string {
	return fmt.Sprintf("%s|%s|%s", strings.ToLower(r.Owner), dns.TypeToString[r.Type], strings.ToLower(r.RDATA))
}

func CanonicalDNSKEY(rr dns.RR) []byte {
	key := rr.(*dns.DNSKEY)
	var b strings.Builder
	b.WriteString(fmt.Sprintf("%d %d %d ", key.Flags, key.Protocol, key.Algorithm))
	b.Write([]byte(key.PublicKey))
	return []byte(b.String())
}

func CanonicalOwner(owner string) string {
	return strings.ToLower(dns.Fqdn(owner))
}
