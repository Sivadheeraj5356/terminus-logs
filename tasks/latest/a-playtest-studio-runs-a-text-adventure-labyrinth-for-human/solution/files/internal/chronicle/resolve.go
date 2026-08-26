// Package chronicle resolves which game-master chronicle markdown file
// governs a given world_id. The chronicle text is later parsed by the
// rules package for @RULE forbidden lines.
package chronicle

import "path/filepath"

// BundledPath is the chronicle shipped with the labyrinth world inside the
// agent image.
const BundledPath = "/app/docs/gm-chronicle.md"

// HiddenWorldsRoot is where verifier-only world fixtures (including their
// own chronicle.md) are mounted, alongside their world.json.
const HiddenWorldsRoot = "/opt/verifier-fixtures/worlds"

// Resolve returns the chronicle path for worldID.
func Resolve(worldID string) string {
	if worldID == "" || worldID == "labyrinth" {
		return BundledPath
	}
	return filepath.Join(HiddenWorldsRoot, worldID, "chronicle.md")
}
