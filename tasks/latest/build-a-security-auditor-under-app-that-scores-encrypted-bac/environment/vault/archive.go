package vault

import "backuptrust/schema"

// ResolveArchivesDir returns the absolute archives directory, honoring EBTA_ARCHIVES_DIR.
func ResolveArchivesDir() (string, error) {
	panic("vault.ResolveArchivesDir not implemented")
}

// LoadArchive reads and validates one archive JSON file.
func LoadArchive(path string) (schema.ArchiveFile, error) {
	panic("vault.LoadArchive not implemented")
}
