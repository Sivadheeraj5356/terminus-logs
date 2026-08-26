package keys

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"

	"github.com/miekg/dns"
)

// KeyTag computes the RFC 4034 key tag for display and BIND interoperability.
func KeyTag(key *dns.DNSKEY) uint16 {
	ac := uint32(key.Flags) + uint32(key.Protocol) + uint32(key.Algorithm)
	pub := []byte(key.PublicKey)
	for i := 0; i < len(pub); i++ {
		if i&1 == 1 {
			ac += uint32(pub[i])
		} else {
			ac += uint32(pub[i]) << 8
		}
	}
	return uint16((ac + (ac >> 16)) & 0xffff)
}

// DurableID returns the durable lineage identifier used for reconciliation.
func DurableID(key *dns.DNSKEY) string {
	return fmt.Sprintf("tag:%d:alg:%d", KeyTag(key), key.Algorithm)
}

// MaterialDigest hashes full DNSKEY RDATA including flags.
func MaterialDigest(key *dns.DNSKEY) string {
	h := sha256.New()
	fmt.Fprintf(h, "%d|%d|%d|%s", key.Flags, key.Protocol, key.Algorithm, key.PublicKey)
	return hex.EncodeToString(h.Sum(nil))
}

func lineageDigest(key *dns.DNSKEY) string {
	h := sha256.New()
	h.Write([]byte{1})
	h.Write([]byte{key.Algorithm})
	h.Write([]byte(key.PublicKey))
	return hex.EncodeToString(h.Sum(nil))
}
