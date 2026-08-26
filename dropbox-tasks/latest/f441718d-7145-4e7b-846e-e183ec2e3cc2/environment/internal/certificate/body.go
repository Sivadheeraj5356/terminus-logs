package certificate

import (
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// BodyMap constructs the canonical certificate body map.
func BodyMap(cert *model.Certificate) map[string]any {
	return map[string]any{
		"version":           cert.Version,
		"workflow_id":       cert.WorkflowID,
		"plan_digest":       cert.PlanDigest,
		"journal_hash":      cert.JournalHash,
		"replay_hash":       cert.ReplayHash,
		"recovery_digest":   cert.RecoveryDigest,
		"verification_hash": cert.VerificationHash,
		"provenance":        cert.Provenance,
	}
}

// BodyBytes returns canonical JSON bytes for the certificate body.
func BodyBytes(cert *model.Certificate) ([]byte, error) {
	return util.CanonicalJSON(BodyMap(cert))
}
