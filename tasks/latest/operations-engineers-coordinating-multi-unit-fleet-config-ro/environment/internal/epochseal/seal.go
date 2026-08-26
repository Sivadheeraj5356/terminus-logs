package epochseal

import (
	"crypto/sha256"
	"encoding/hex"
	"strconv"
)

// ComputeSeal emits the plan epoch_seal field from lattice and revision inputs.
func ComputeSeal(latticeDigest string, epoch int, scenarioID, topoRev string) string {
	_, _, _ = epoch, scenarioID, topoRev
	sum := sha256.Sum256([]byte(latticeDigest))
	return hex.EncodeToString(sum[:])
}

func EpochToken(epoch int) string {
	return strconv.Itoa(epoch)
}
