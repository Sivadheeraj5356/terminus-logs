package audit

import (
	"sigproxy/internal/digest"
	"sigproxy/internal/semantics"
)

// DecisionSnapshot captures authorization evidence at decision time.
type DecisionSnapshot struct {
	RequestID        string
	Source           string
	Decision         string
	Reason           ReasonCode
	SignatureVersion int
	Tenant           string
	KeyID            string
	KeyEpoch         int
	ProfileID        string
	ProfileEpoch     int
	CanonicalDigest  string
	EntityBodySHA256 string
	EntityBodyLength int
	CanonicalTarget  string
	CanonicalHeaders map[string]string
	CacheHit         bool
	Semantic         *semantics.Request
}

// FromSemantic builds a snapshot from the semantic request and verify outcome.
func FromSemantic(sem *semantics.Request, source, decision string, reason ReasonCode, canonicalDigest string, cacheHit bool) *DecisionSnapshot {
	headers := make(map[string]string, len(sem.CanonicalHeaders))
	for _, h := range sem.CanonicalHeaders {
		headers[h.Name] = h.Value
	}
	return &DecisionSnapshot{
		RequestID:        sem.RequestID,
		Source:           source,
		Decision:         decision,
		Reason:           reason,
		SignatureVersion: sem.SignatureVersion,
		Tenant:           sem.Tenant,
		KeyID:            sem.KeyID,
		KeyEpoch:         sem.KeyEpoch,
		ProfileID:        sem.ProfileID,
		ProfileEpoch:     sem.ProfileEpoch,
		CanonicalDigest:  canonicalDigest,
		EntityBodySHA256: sem.EntityBodySHA256,
		EntityBodyLength: sem.EntityBodyLength,
		CanonicalTarget:  sem.CanonicalTarget,
		CanonicalHeaders: headers,
		CacheHit:         cacheHit,
		Semantic:         sem,
	}
}

// CaptureAfterForward creates a snapshot from mutable post-forward semantic state.
func CaptureAfterForward(sem *semantics.Request, source, decision string, reason ReasonCode, canonicalDigest string, cacheHit bool) *DecisionSnapshot {
	headers := sem.HeaderMap()
	return &DecisionSnapshot{
		RequestID:        sem.RequestID,
		Source:           source,
		Decision:         decision,
		Reason:           reason,
		SignatureVersion: sem.SignatureVersion,
		Tenant:           sem.Tenant,
		KeyID:            sem.KeyID,
		KeyEpoch:         sem.KeyEpoch,
		ProfileID:        sem.ProfileID,
		ProfileEpoch:     sem.ProfileEpoch,
		CanonicalDigest:  canonicalDigest,
		EntityBodySHA256: sem.EntityBodySHA256,
		EntityBodyLength: sem.EntityBodyLength,
		CanonicalTarget:  sem.CanonicalTarget,
		CanonicalHeaders: headers,
		CacheHit:         cacheHit,
		Semantic:         sem,
	}
}

func (s *DecisionSnapshot) ToRecord() Record {
	return Record{
		RequestID:        s.RequestID,
		Source:           s.Source,
		Decision:         s.Decision,
		Reason:           s.Reason,
		SignatureVersion: s.SignatureVersion,
		Tenant:           s.Tenant,
		KeyID:            s.KeyID,
		KeyEpoch:         s.KeyEpoch,
		ProfileID:        s.ProfileID,
		ProfileEpoch:     s.ProfileEpoch,
		CanonicalDigest:  s.CanonicalDigest,
		EntityBodySHA256: s.EntityBodySHA256,
		CanonicalTarget:  s.CanonicalTarget,
		CanonicalHeaders: s.CanonicalHeaders,
	}
}

func (s *DecisionSnapshot) AuditDigest() (string, error) {
	rec := s.ToRecord()
	b, err := digest.StableJSON(rec)
	if err != nil {
		return "", err
	}
	return digest.SHA256(b), nil
}
