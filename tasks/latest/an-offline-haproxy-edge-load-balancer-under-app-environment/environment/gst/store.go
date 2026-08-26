package gst

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"qxhub/pth"
)

// WriteGeneration persists one immutable generation directory with its
// manifest bytes and detached seal file.
func WriteGeneration(gen int, manifest []byte, seal string) error {
	dir := filepath.Join(pth.GenerationsDir(), strconv.Itoa(gen))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, "manifest.json"), manifest, 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(dir, "MSEAL"), []byte(seal+"\n"), 0o644); err != nil {
		return err
	}
	return os.WriteFile(pth.CurrentPath(), []byte(fmt.Sprintf("%d\n", gen)), 0o644)
}

// ReadCurrent returns the current generation pointer, 0 when unset.
func ReadCurrent() int {
	raw, err := os.ReadFile(pth.CurrentPath())
	if err != nil {
		return 0
	}
	n, err := strconv.Atoi(strings.TrimSpace(string(raw)))
	if err != nil {
		return 0
	}
	return n
}

// SetCurrent rewrites the current generation pointer.
func SetCurrent(gen int) error {
	return os.WriteFile(pth.CurrentPath(), []byte(fmt.Sprintf("%d\n", gen)), 0o644)
}

// SealBytes is the manifest seal formula: sha256 hex over the exact bytes.
func SealBytes(raw []byte) string {
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

// ListGenerations returns the recorded generation numbers in ascending order.
func ListGenerations() []int {
	entries, err := os.ReadDir(pth.GenerationsDir())
	if err != nil {
		return nil
	}
	var out []int
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		if n, err := strconv.Atoi(e.Name()); err == nil {
			out = append(out, n)
		}
	}
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j-1] > out[j]; j-- {
			out[j-1], out[j] = out[j], out[j-1]
		}
	}
	return out
}
