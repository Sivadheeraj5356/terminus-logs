package validate

import (
	"fmt"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// CertificateShape checks required certificate fields are present.
func CertificateShape(cert *model.Certificate) error {
	if cert == nil {
		return fmt.Errorf("nil certificate")
	}
	if cert.Version != "recovery-certificate-v1" {
		return fmt.Errorf("unexpected version %q", cert.Version)
	}
	required := []string{
		cert.WorkflowID, cert.PlanDigest, cert.JournalHash, cert.ReplayHash,
		cert.RecoveryDigest, cert.VerificationHash, cert.BodyDigest, cert.Signature,
	}
	for _, v := range required {
		if strings.TrimSpace(v) == "" {
			return fmt.Errorf("certificate missing required digest field")
		}
	}
	if len(cert.Signature) != 64 {
		return fmt.Errorf("signature must be 64 hex chars")
	}
	if len(cert.BodyDigest) != 64 {
		return fmt.Errorf("body digest must be 64 hex chars")
	}
	return nil
}

// ReportHealthy ensures verification report has no issues.
func ReportHealthy(r *model.VerificationReport) error {
	if r == nil {
		return fmt.Errorf("nil report")
	}
	if !(r.LineageOK && r.GraphOK && r.CheckpointOK && r.ReplayOK && r.HashOK) {
		return fmt.Errorf("report not healthy: %#v", r.Issues)
	}
	if len(r.Issues) != 0 {
		return fmt.Errorf("issues present: %v", r.Issues)
	}
	return nil
}
