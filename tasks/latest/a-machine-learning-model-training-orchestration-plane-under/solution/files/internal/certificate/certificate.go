package certificate

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Issue creates a recovery certificate bound to plan/journal/replay/recovery/verification digests.
func Issue(
	wf *model.Workflow,
	plan *model.ExecutionPlan,
	rec *model.ExecutionRecord,
	rr *model.ReplayRecord,
	recovery *model.RecoveryResult,
	report *model.VerificationReport,
	token string,
	epoch string,
) (*model.Certificate, error) {
	if token == "" {
		return nil, fmt.Errorf("signing token required")
	}
	prov := map[string]string{
		"workflow_name": wf.Name,
		"workflow_ver":  wf.Version,
		"seed":          "bound",
	}
	body := map[string]any{
		"version":           "recovery-certificate-v1",
		"workflow_id":       wf.ID,
		"plan_digest":       plan.Digest,
		"journal_hash":      rec.JournalHash,
		"replay_hash":       rr.ReplayHash,
		"recovery_digest":   recovery.RecoveryDigest,
		"verification_hash": report.VerificationHash,
		"provenance":        prov,
	}
	payload, err := util.CanonicalJSON(body)
	if err != nil {
		return nil, err
	}
	bodyDigest := hash.DomainHash("recovery-certificate-v1", payload)
	mac := hmac.New(sha256.New, []byte(token))
	_, _ = mac.Write(payload)
	sig := hex.EncodeToString(mac.Sum(nil))

	issued, _ := util.OffsetTimestamp(epoch, 0)
	cert := &model.Certificate{
		Version: "recovery-certificate-v1",
		WorkflowID: wf.ID, PlanDigest: plan.Digest, JournalHash: rec.JournalHash,
		ReplayHash: rr.ReplayHash, RecoveryDigest: recovery.RecoveryDigest,
		VerificationHash: report.VerificationHash,
		BodyDigest: bodyDigest, Signature: sig, Provenance: prov, IssuedAt: issued,
	}
	return cert, nil
}

// Verify checks certificate signature and body digest.
func Verify(cert *model.Certificate, token string) bool {
	if cert == nil || token == "" {
		return false
	}
	body := map[string]any{
		"version":           cert.Version,
		"workflow_id":       cert.WorkflowID,
		"plan_digest":       cert.PlanDigest,
		"journal_hash":      cert.JournalHash,
		"replay_hash":       cert.ReplayHash,
		"recovery_digest":   cert.RecoveryDigest,
		"verification_hash": cert.VerificationHash,
		"provenance":        cert.Provenance,
	}
	payload, err := util.CanonicalJSON(body)
	if err != nil {
		return false
	}
	bodyDigest := hash.DomainHash("recovery-certificate-v1", payload)
	if bodyDigest != cert.BodyDigest {
		return false
	}
	mac := hmac.New(sha256.New, []byte(token))
	_, _ = mac.Write(payload)
	sig := hex.EncodeToString(mac.Sum(nil))
	return sig == cert.Signature
}

// LoadToken reads the HMAC signing token from disk.
func LoadToken(path string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(bytesTrim(b)), nil
}

func bytesTrim(b []byte) []byte {
	for len(b) > 0 && (b[len(b)-1] == '\n' || b[len(b)-1] == '\r' || b[len(b)-1] == ' ') {
		b = b[:len(b)-1]
	}
	return b
}
