package health

import (
	"fmt"
	"os"
	"path/filepath"
)

// SidecarCount tallies PID sidecar files for inventory-style probes.
func SidecarCount(dir string) (int, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0, err
	}
	n := 0
	for _, ent := range entries {
		if ent.IsDir() {
			continue
		}
		n++
	}
	return n, nil
}

// PublishedSidecarCount returns files directly under the published directory.
func PublishedSidecarCount(published string) int {
	n, err := SidecarCount(published)
	if err != nil {
		return 0
	}
	return n
}

// FixtureSidecarCount returns sidecar cardinality from a fixture gen tree.
func FixtureSidecarCount(fixtures string, gen int) int {
	dir := filepath.Join(fixtures, fmtGen(gen))
	n, err := SidecarCount(dir)
	if err != nil {
		return 0
	}
	return n
}

func fmtGen(gen int) string {
	return fmt.Sprintf("gen%d", gen)
}
