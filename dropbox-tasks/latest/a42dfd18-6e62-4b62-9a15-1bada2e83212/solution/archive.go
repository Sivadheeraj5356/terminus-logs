package vault

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"backuptrust/schema"
)

var shellMeta = []string{"`", ";", "|", "$", "&", "\n", "\r"}

// ResolveArchivesDir returns the absolute archives directory, honoring EBTA_ARCHIVES_DIR.
func ResolveArchivesDir() (string, error) {
	raw := os.Getenv("EBTA_ARCHIVES_DIR")
	if raw == "" {
		return filepath.Clean("/app/archives"), nil
	}
	if !filepath.IsAbs(raw) {
		return "", errors.New("EBTA_ARCHIVES_DIR must be absolute")
	}
	for _, m := range shellMeta {
		if strings.Contains(raw, m) {
			return "", errors.New("EBTA_ARCHIVES_DIR contains shell metacharacters")
		}
	}
	resolved, err := filepath.EvalSymlinks(raw)
	if err != nil {
		return "", fmt.Errorf("EBTA_ARCHIVES_DIR resolve: %w", err)
	}
	if !filepath.IsAbs(resolved) {
		return "", errors.New("EBTA_ARCHIVES_DIR resolved path must be absolute")
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return "", fmt.Errorf("EBTA_ARCHIVES_DIR stat: %w", err)
	}
	if !info.IsDir() {
		return "", errors.New("EBTA_ARCHIVES_DIR is not a directory")
	}
	f, err := os.Open(resolved)
	if err != nil {
		return "", fmt.Errorf("EBTA_ARCHIVES_DIR not readable: %w", err)
	}
	_ = f.Close()
	return resolved, nil
}

// LoadArchive reads and validates one archive JSON file.
func LoadArchive(path string) (schema.ArchiveFile, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return schema.ArchiveFile{}, err
	}
	var a schema.ArchiveFile
	if err := json.Unmarshal(raw, &a); err != nil {
		return schema.ArchiveFile{}, err
	}
	base := strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	if a.ArchiveID != base {
		return schema.ArchiveFile{}, fmt.Errorf("archive_id %q does not match file %q", a.ArchiveID, base)
	}
	return a, nil
}
