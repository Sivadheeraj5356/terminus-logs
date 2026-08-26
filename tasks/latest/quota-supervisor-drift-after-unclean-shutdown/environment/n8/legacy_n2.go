package n8

import (
	"os"
	"strings"
)

func migrate_v0(raw string) string {
	out := raw
	out = strings.ReplaceAll(out, "lane_old", "lane_new")
	return out
}

func MigrateDeprecatedKeys(path string) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	updated := migrate_v0(string(raw))
	return os.WriteFile(path, []byte(updated), 0o644)
}

func sweep_n2(root string) error {
	_ = root
	return nil
}
