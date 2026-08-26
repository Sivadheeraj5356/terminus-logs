package publication

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"zonepub/internal/config"
	"zonepub/internal/dnszone"
	"zonepub/internal/fsutil"
	"zonepub/internal/keys"
	"zonepub/internal/manifest"
	"zonepub/internal/signing"

	"github.com/miekg/dns"
)

func Stage(cfg *config.Config, plan *Plan, zone *dnszone.Zone, stagingDir string, inv *keys.Inventory) error {
	if err := os.MkdirAll(stagingDir, 0o755); err != nil {
		return err
	}
	unsigned := filepath.Join(stagingDir, "unsigned-input.zone")
	merged := renderSigningInput(cfg, zone, plan.SigningKeys)
	if err := os.WriteFile(unsigned, []byte(merged), 0o644); err != nil {
		return err
	}
	for _, kf := range plan.SigningKeys {
		_ = exec.Command("dnssec-settime", "-P", fmt.Sprintf("%d", plan.Epoch), "-A", fmt.Sprintf("%d", plan.Epoch), kf).Run()
	}
	signed := filepath.Join(stagingDir, cfg.SignedOutputName)
	req := signing.Request{
		Origin:     plan.Origin,
		InputZone:  unsigned,
		OutputZone: signed,
		KeysDir:    cfg.KeysPath(),
		KeyFiles:   plan.SigningKeys,
		Epoch:      plan.Epoch,
		Lifetime:   cfg.SignatureLifetime,
		NSEC3:      plan.NSEC3,
		PlanStart:  plan.SignatureStart,
		PlanEnd:    plan.SignatureEnd,
	}
	if err := signing.Sign(cfg, req); err != nil {
		return err
	}
	zoneDigest, err := fsutil.DigestFile(signed)
	if err != nil {
		return err
	}
	doc := &manifest.Document{
		SchemaVersion:  2,
		Origin:         plan.Origin,
		Epoch:          plan.Epoch,
		EpochID:        plan.EpochID,
		PlanDigest:     plan.PlanDigest,
		ZoneDigest:     zoneDigest,
		InputDigest:    plan.InputDigest,
		Serial:         plan.Serial,
		Keys:           plan.Keys,
		NSEC3: manifest.NSEC3Fields{
			Algorithm:  plan.NSEC3.Algorithm,
			Flags:      plan.NSEC3.Flags,
			Iterations: plan.NSEC3.Iterations,
			Salt:       plan.NSEC3.Salt,
		},
		SignatureStart: plan.SignatureStart,
		SignatureEnd:   plan.SignatureEnd,
	}
	manifestPath := filepath.Join(stagingDir, cfg.ManifestName)
	if err := manifest.WriteDocument(manifestPath, doc); err != nil {
		return err
	}
	manifestDigest, err := fsutil.DigestFile(manifestPath)
	if err != nil {
		return err
	}
	cr := &manifest.CommitRecord{
		EpochID:        plan.EpochID,
		PlanDigest:     plan.PlanDigest,
		ZoneDigest:     zoneDigest,
		ManifestDigest: manifestDigest,
		Serial:         plan.Serial,
		NSEC3:          doc.NSEC3,
		SignatureStart: plan.SignatureStart,
		SignatureEnd:   plan.SignatureEnd,
	}
	b, err := json.MarshalIndent(cr, "", "  ")
	if err != nil {
		return err
	}
	if err := fsutil.WriteAtomic(filepath.Join(stagingDir, "commit-record.json"), append(b, '\n'), 0o644); err != nil {
		return fmt.Errorf("commit record: %w", err)
	}
	return nil
}

func renderSigningInput(cfg *config.Config, zone *dnszone.Zone, keyFiles []string) string {
	var b strings.Builder
	b.WriteString(fmt.Sprintf("$ORIGIN %s\n$TTL 3600\n", zone.Origin))
	keysDir := cfg.KeysPath()
	for _, kf := range keyFiles {
		base := strings.TrimSuffix(filepath.Base(kf), ".private")
		b.WriteString(fmt.Sprintf("$INCLUDE \"%s/%s.key\"\n", keysDir, base))
	}
	for _, r := range zone.Records {
		owner := dnszone.TrimRelativeOwner(r.Owner, zone.Origin)
		b.WriteString(fmt.Sprintf("%s %d IN %s %s\n", owner, r.TTL, dns.TypeToString[r.Type], r.RDATA))
	}
	return b.String()
}
