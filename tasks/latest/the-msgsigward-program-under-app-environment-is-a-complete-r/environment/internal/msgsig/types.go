// Package msgsig decides whether an immutable HTTP request and its RFC 9421
// message signature (Signature / Signature-Input headers) establish an
// authenticated, adequately-covered, fresh request under a trusted keyset, or
// whether the request must be rejected (forged, under-covered, replayed,
// body-substituted, or algorithm-downgraded).
//
// The evidence is read-only: the request, its headers (including the received
// Signature-Input and Signature fields), the trusted keyset, and a fixed
// evaluation time are all immutable inputs. See docs/security-spec.md for the
// authoritative contract, the signature-base construction, the reason
// vocabulary, and the decision-line format.
package msgsig

import (
	"encoding/json"
	"errors"
)

// Verdicts. The decision line is "<verdict> <selector> <covered>": <selector>
// is the accepted signature's label for a verified request, or the reason code
// for a rejected one. See docs/security-spec.md for the full reason vocabulary
// and the covered-list format.
const (
	Verified = "verified" // a candidate signature verifies and the policy accepts it
	Rejected = "rejected" // no candidate signature is an authenticated, adequate signature
)

// FieldValue is one HTTP header field's value. A field may be given as a single
// JSON string (one field line) or as a JSON array of strings (the same field
// name appearing on several lines). Lines preserves that order.
type FieldValue struct {
	Lines []string
}

// UnmarshalJSON accepts either a string or an array of strings.
func (f *FieldValue) UnmarshalJSON(b []byte) error {
	var s string
	if err := json.Unmarshal(b, &s); err == nil {
		f.Lines = []string{s}
		return nil
	}
	var a []string
	if err := json.Unmarshal(b, &a); err == nil {
		f.Lines = a
		return nil
	}
	return errors.New("header value must be a string or an array of strings")
}

// One returns the single field line, or an error if the field is multi-valued
// or empty (used for the Signature / Signature-Input dictionary fields, which
// are single structured-field values).
func (f FieldValue) One() (string, error) {
	if len(f.Lines) != 1 {
		return "", errors.New("expected a single-valued header field")
	}
	return f.Lines[0], nil
}

// Key is one trusted key, selected by keyid. Alg is the algorithm bound to the
// key ("ed25519" or "hmac-sha256"). Public is the hex-encoded 32-byte ed25519
// public key (asymmetric keys). Secret is the hex-encoded HMAC key (symmetric
// keys). Exactly one of Public/Secret is set per the key's Alg.
type Key struct {
	Alg    string `json:"alg"`
	Public string `json:"public,omitempty"`
	Secret string `json:"secret,omitempty"`
}

// Message is the immutable HTTP request under evaluation. Query is the raw query
// string WITHOUT a leading '?', and is "" when the request has no query. Headers
// are lowercase field names to their field values, and include the received
// "signature-input" and "signature" fields. Body is the raw request body (which
// may be empty).
type Message struct {
	Method    string                `json:"method"`
	Authority string                `json:"authority"`
	Path      string                `json:"path"`
	Query     string                `json:"query"`
	Headers   map[string]FieldValue `json:"headers"`
	Body      string                `json:"body"`
}

// Input is one immutable signature-verification bundle. Keys is the trusted
// keyset by keyid; Now is the fixed evaluation time (unix seconds) against which
// created/expires are judged; Message is the request plus its signature headers.
type Input struct {
	Keys    map[string]Key `json:"keys"`
	Now     int64          `json:"now"`
	Message Message        `json:"message"`
}
