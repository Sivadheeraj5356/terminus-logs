package signature

import (
	"testing"

	"sigproxy/internal/semantics"
)

func TestLegacyMessageDistinctFromCurrent(t *testing.T) {
	sem := &semantics.Request{
		Tenant:           "demo",
		KeyID:            "k1",
		KeyEpoch:         1,
		ProfileID:        "legacy-2024",
		ProfileEpoch:     1,
		Method:           "GET",
		Authority:        "example.local",
		CanonicalTarget:  "/health",
		CanonicalHeaders: []semantics.HeaderField{{Name: "host", Value: "example.local"}},
		EntityBodySHA256: semantics.BodyDigest(nil),
		EntityBodyLength: 0,
		RequestNonce:     "n1",
	}
	legacy, err := BuildLegacyV1(sem)
	if err != nil {
		t.Fatal(err)
	}
	sem.SignatureVersion = 2
	sem.ProfileID = "current-2026"
	current, err := BuildCurrentV2(sem)
	if err != nil {
		t.Fatal(err)
	}
	if legacy == current {
		t.Fatal("legacy and current messages must differ")
	}
	if len(legacy) < 20 || len(current) < 20 {
		t.Fatal("messages too short")
	}
}
