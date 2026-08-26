package h2

import "conformal-coverage-witness-pack/m9f"

func FoldCover(pfx string, blob []byte) string {
	return m9f.FoldCoverM9(pfx, blob)
}
