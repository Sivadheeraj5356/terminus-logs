package publication

import (
	"fmt"
	"path/filepath"

	"zonepub/internal/config"
	"zonepub/internal/fsutil"
	"zonepub/internal/journal"
	"zonepub/internal/manifest"
)

// Commit promotes staged artifacts and appends journal history.
func Commit(cfg *config.Config, plan *Plan, stagingDir, outputDir string, records []journal.Record) error {
	signedName := cfg.SignedOutputName
	manifestName := cfg.ManifestName
	stagedZone := filepath.Join(stagingDir, signedName)
	stagedManifest := filepath.Join(stagingDir, manifestName)
	outZone := filepath.Join(outputDir, signedName)
	outManifest := filepath.Join(outputDir, manifestName)

	// promote zone first (crash window before manifest)
	if err := fsutil.CopyFile(stagedZone, outZone); err != nil {
		return fmt.Errorf("promote zone: %w", err)
	}
	if err := fsutil.CopyFile(stagedManifest, outManifest); err != nil {
		return fmt.Errorf("promote manifest: %w", err)
	}
	zoneDigest, _ := fsutil.DigestFile(outZone)
	manifestDigest, _ := fsutil.DigestFile(outManifest)
	rec := journal.NewRecord(journal.NextSequence(records), plan.EpochID, plan.PlanDigest, journal.PhaseAccepted)
	rec.Serial = plan.Serial
	rec.ZoneDigest = zoneDigest
	rec.ManifestDigest = manifestDigest
	rec.NSEC3 = manifest.NSEC3Fields{
		Algorithm:  plan.NSEC3.Algorithm,
		Flags:      plan.NSEC3.Flags,
		Iterations: plan.NSEC3.Iterations,
		Salt:       plan.NSEC3.Salt,
	}
	for _, k := range plan.Keys {
		rec.Keys = append(rec.Keys, manifest.JournalKeyState{
			LineageID: k.LineageID,
			Role:      k.Role,
			Status:    k.Status,
			KeyTag:    k.KeyTag,
		})
	}
	if err := journal.Append(cfg.JournalPath(), rec); err != nil {
		return fmt.Errorf("journal: %w", err)
	}
	return nil
}
