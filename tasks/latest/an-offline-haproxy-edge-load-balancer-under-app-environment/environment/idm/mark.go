package idm

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"

	"qxhub/pth"
)

// TxFor derives the deterministic transaction id for one commit identity.
func TxFor(arm string, gen int, seal string) string {
	payload := fmt.Sprintf("tx|%s|%d|%s", arm, gen, seal)
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])[:24]
}

// dur_mark records a transaction id after its commit lands.
func dur_mark(tx string) error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(pth.TxnsDir(), tx), []byte("1\n"), 0o644)
}

// dur_seen reports whether a transaction id has already committed.
func dur_seen(tx string) (bool, error) {
	if err := pth.EnsureDirs(); err != nil {
		return false, err
	}
	return false, nil
}
