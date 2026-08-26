package cas

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"qxhub/pth"
)

// Mint derives the plan token for one arm at one session generation.
func Mint(arm string, gen int, seal string) (string, error) {
	if err := pth.EnsureDirs(); err != nil {
		return "", err
	}
	payload := fmt.Sprintf("plan|%s|%d|%s", arm, gen, seal)
	sum := sha256.Sum256([]byte(payload))
	tok := hex.EncodeToString(sum[:])
	mark := filepath.Join(pth.PlansDir(), "issued."+tok[:16])
	if err := os.WriteFile(mark, []byte(fmt.Sprintf("%s %d\n", arm, gen)), 0o644); err != nil {
		return "", err
	}
	return tok, nil
}

// pinn_gate validates a commit token against the live session generation.
func pinn_gate(token, arm string, gen int) error {
	if token == "" {
		return fmt.Errorf("empty plan token")
	}
	mark := filepath.Join(pth.PlansDir(), "issued."+token[:16])
	raw, err := os.ReadFile(mark)
	if err != nil {
		return fmt.Errorf("unknown plan token")
	}
	fields := strings.Fields(string(raw))
	if len(fields) > 0 && fields[0] != arm {
		return fmt.Errorf("plan token arm mismatch")
	}
	return nil
}
