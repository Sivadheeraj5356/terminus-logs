package spool

import (
	"encoding/hex"
	"testing"

	"sigproxy/internal/semantics"
)

func TestSealRoundTrip(t *testing.T) {
	key := []byte("demo-spool-seal-key-32-bytes!!")
	sem := &semantics.Request{
		RequestID:        "r1",
		ProfileID:        "current-2026",
		ProfileEpoch:     1,
		CanonicalTarget:  "/api",
		EntityBodySHA256: semantics.BodyDigest([]byte("hi")),
	}
	rec := NewRecord("r1", 0, "wd", sem, "v2 abc", "dd")
	seal, err := ComputeSeal(rec, key)
	if err != nil {
		t.Fatal(err)
	}
	rec.Seal = seal
	if !VerifySeal(rec, key) {
		t.Fatal("seal verify failed")
	}
	rec.State = StateCompleted
	if VerifySeal(rec, key) {
		t.Fatal("seal should fail after state change without reseal")
	}
	_ = hex.EncodeToString(key)
}
