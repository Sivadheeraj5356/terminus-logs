package sim

import "chronctl/internal/cord"

func fold_head(priorHex string, localSealHex string) string {
	return cord.KnitA(priorHex, localSealHex)
}
