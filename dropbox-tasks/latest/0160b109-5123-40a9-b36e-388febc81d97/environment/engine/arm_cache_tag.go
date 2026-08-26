package engine

import (
	"os"
	"path/filepath"
	"strings"
)

// CacheArmTagPath is the durable arm marker beside cache bins.
func CacheArmTagPath(cacheDir string) string {
	return filepath.Join(cacheDir, "arm_tag")
}

// WriteCacheArmTag records which arm minted the current cache tree.
func WriteCacheArmTag(cacheDir, arm string) error {
	if err := os.MkdirAll(cacheDir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(CacheArmTagPath(cacheDir), []byte(strings.TrimSpace(arm)+"\n"), 0o644)
}

// ReadCacheArmTag returns the arm recorded for the cache tree.
func ReadCacheArmTag(cacheDir string) (string, bool) {
	raw, err := os.ReadFile(CacheArmTagPath(cacheDir))
	if err != nil {
		return "", false
	}
	arm := strings.TrimSpace(string(raw))
	return arm, arm != ""
}

// ShouldAcceptCache reports whether bins under cacheDir may be trusted for arm.
func ShouldAcceptCache(cacheDir, arm string) bool {
	entries, err := os.ReadDir(cacheDir)
	if err != nil {
		return false
	}
	hasBin := false
	for _, ent := range entries {
		if strings.HasSuffix(ent.Name(), ".bin") {
			hasBin = true
			break
		}
	}
	return hasBin
}
