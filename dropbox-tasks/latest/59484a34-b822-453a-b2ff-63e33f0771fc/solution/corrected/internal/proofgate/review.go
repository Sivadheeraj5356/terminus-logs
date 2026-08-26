package proofgate

import "github.com/privco/ctpki/internal/pkitypes"

func MissingProofDisposition() string {
	return "needs_review"
}

func HasProof(proofs map[string]pkitypes.InclusionProof, key string) bool {
	_, ok := proofs[key]
	return ok
}
