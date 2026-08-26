package verify

import "gachaudit/internal/hashx"

func SeedHashOK(serverSeed, claimed string) bool {
	decoded, err := hashx.DecodeHexLoose(serverSeed)
	if err == nil && len(decoded) > 0 {
		return hashx.SHA256Hex(decoded) == claimed
	}
	return hashx.SHA256Hex([]byte(serverSeed)) == claimed
}
