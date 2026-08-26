package signature

import (
	"fmt"
	"strings"

	"sigproxy/internal/semantics"
)

// Message is the canonical signing string components.
type Message struct {
	Version int
	Lines   []string
	Raw     string
}

func BuildMessage(sem *semantics.Request, version int) (*Message, error) {
	switch version {
	case 1:
		return buildLegacyV1(sem)
	case 2:
		return buildCurrentV2(sem)
	default:
		return nil, fmt.Errorf("unsupported signature version %d", version)
	}
}

func buildCurrentV2(sem *semantics.Request) (*Message, error) {
	var b strings.Builder
	b.WriteString("LOCAL-SIG-V2\n")
	fmt.Fprintf(&b, "profile:%s@%d\n", sem.ProfileID, sem.ProfileEpoch)
	fmt.Fprintf(&b, "key:%s/%s@%d\n", sem.Tenant, sem.KeyID, sem.KeyEpoch)
	fmt.Fprintf(&b, "method:%s\n", sem.Method)
	fmt.Fprintf(&b, "authority:%s\n", sem.Authority)
	fmt.Fprintf(&b, "target:%s\n", sem.CanonicalTarget)
	fmt.Fprintf(&b, "headers:%d\n", len(sem.CanonicalHeaders))
	for _, h := range sem.CanonicalHeaders {
		fmt.Fprintf(&b, "%s:%s\n", h.Name, h.Value)
	}
	fmt.Fprintf(&b, "body-sha256:%s\n", sem.EntityBodySHA256)
	fmt.Fprintf(&b, "body-length:%d\n", sem.EntityBodyLength)
	fmt.Fprintf(&b, "nonce:%s\n", sem.RequestNonce)
	raw := b.String()
	return &Message{Version: 2, Lines: strings.Split(strings.TrimSuffix(raw, "\n"), "\n"), Raw: raw}, nil
}

func buildLegacyV1(sem *semantics.Request) (*Message, error) {
	var b strings.Builder
	b.WriteString("LOCAL-SIG-V1\n")
	fmt.Fprintf(&b, "tenant:%s\n", sem.Tenant)
	fmt.Fprintf(&b, "key:%s@%d\n", sem.KeyID, sem.KeyEpoch)
	fmt.Fprintf(&b, "profile:%s\n", sem.ProfileID)
	fmt.Fprintf(&b, "%s %s\n", sem.Method, sem.CanonicalTarget)
	fmt.Fprintf(&b, "host:%s\n", sem.Authority)
	for _, h := range sem.CanonicalHeaders {
		fmt.Fprintf(&b, "h:%s=%s\n", h.Name, h.Value)
	}
	fmt.Fprintf(&b, "body:%s:%d\n", sem.EntityBodySHA256, sem.EntityBodyLength)
	fmt.Fprintf(&b, "nonce:%s\n", sem.RequestNonce)
	raw := b.String()
	return &Message{Version: 1, Lines: strings.Split(strings.TrimSuffix(raw, "\n"), "\n"), Raw: raw}, nil
}
