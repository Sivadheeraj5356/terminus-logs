package journalspan

import (
	"crypto/sha256"
	"fmt"
)

func RowCheckpointSeal(journalTail, fixtureLabel string, observed int) string {
	payload := fmt.Sprintf("%s|%s|%d", journalTail, fixtureLabel, observed)
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum)[:32]
}
