package ctproof

import (
	"github.com/privco/ctpki/internal/merkle"
	"github.com/privco/ctpki/internal/pkitypes"
)

func ProofValid(entry pkitypes.CTEntry, proof pkitypes.InclusionProof, sth pkitypes.STH) bool {
	if proof.Serial != entry.Serial {
		return false
	}
	if proof.TreeSize != sth.TreeSize {
		return false
	}
	return merkle.VerifyPath(entry.LeafHash, entry.LeafIndex, proof.Path, sth.RootHash, proof.TreeSize)
}
