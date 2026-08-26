package pipeline

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"modgate/internal/annex"
	"modgate/internal/conflict"
	"modgate/internal/digest"
	"modgate/internal/exclude"
	"modgate/internal/manifest"
	"modgate/internal/models"
	"modgate/internal/modlock"
	"modgate/internal/policy"
	"modgate/internal/proxyclient"
	"modgate/internal/snapshot"
)

func Run(manifestPath, outDir string) error {
	m, err := manifest.Load(manifestPath)
	if err != nil {
		return err
	}
	root := manifest.BatchRoot(manifestPath)
	pins, err := modlock.Load(manifest.Resolve(root, m.ModuleLockPath))
	if err != nil {
		return err
	}
	snap, err := snapshot.Load(manifest.Resolve(root, m.SnapshotPath))
	if err != nil {
		return err
	}
	conflicts, err := conflict.Load(manifest.Resolve(root, m.ConflictReportPath))
	if err != nil {
		return err
	}
	excludes, err := exclude.Load(manifest.Resolve(root, m.ExcludeOverlayPath))
	if err != nil {
		return err
	}
	annexPath := manifest.Resolve(root, m.CorpusAnnexPath)
	matchBin := manifest.Resolve(root, m.RetractmatchBin)
	floorBin := manifest.Resolve(root, m.GofloorBin)
	client := proxyclient.New(m.ProxyAPIBase, m.SumdbAPIBase, matchBin, floorBin, m.ToolchainDeclared, snap)

	rows := make([]models.IntegrityRow, 0, len(pins))
	liveRefreshes := 0
	waiverHits := 0
	staleOverrides := 0
	retractHits := 0
	checksumFailures := 0
	toolchainBlocks := 0
	excludeSkips := 0
	transitiveWarns := 0

	for _, pin := range pins {
		pred := conflicts[pin.ModID]
		isConflict := pred.RefreshRetract || pred.RefreshSum
		if isConflict {
			liveRefreshes++
		}
		_, excluded := excludes[pin.ModulePath]
		probe := client.Resolve(pin, pred)
		if isConflict {
			se := snap[pin.ModID]
			snapFloor := floorOK(floorBin, m.ToolchainDeclared, pin.GoFloor)
			snapViol := se.Retracted || pin.DeclaredHash != se.ZipHash || !snapFloor
			liveViol := false
			if !excluded {
				liveViol = probe.Retracted || !probe.ChecksumOK || !probe.GoFloorOK
			}
			if snapViol != liveViol {
				staleOverrides++
			}
		}
		if annex.InScopeWaiver(annexPath, pin.ModulePath, m.ModuleBatchID) {
			waiverHits++
		}
		row := policy.BuildRow(pin, probe, pred, excluded, m.PolicyTrack, m.ModuleBatchID, annexPath)
		if row.Retracted {
			retractHits++
		}
		if !row.ChecksumOK {
			checksumFailures++
		}
		if row.PolicyBasis == "toolchain_block" {
			toolchainBlocks++
		}
		if row.PolicyBasis == "exclude_skip" {
			excludeSkips++
		}
		if row.PolicyBasis == "retract_warn_transitive" {
			transitiveWarns++
		}
		rows = append(rows, row)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].ModID < rows[j].ModID })

	gateStatus := "pass"
	for _, row := range rows {
		if row.GateAction == "block" {
			gateStatus = "block"
			break
		}
		if row.GateAction == "warn" && gateStatus == "pass" {
			gateStatus = "warn"
		}
	}

	exportDigest, pinDigests := digest.ExportDigest(rows)

	cert := models.Certificate{
		Status:            "MODGATE_OK",
		ModuleBatchID:     m.ModuleBatchID,
		PolicyTrack:       m.PolicyTrack,
		ToolchainDeclared: m.ToolchainDeclared,
		GateStatus:        gateStatus,
		RecordCount:       len(rows),
		LiveRefreshes:     liveRefreshes,
		WaiverHits:        waiverHits,
		StaleOverrides:    staleOverrides,
		RetractHits:       retractHits,
		ChecksumFailures:  checksumFailures,
		ToolchainBlocks:   toolchainBlocks,
		ExcludeSkips:      excludeSkips,
		TransitiveWarns:   transitiveWarns,
		ChainDigest:       digest.Of(rows),
		ExportDigest:      exportDigest,
		MemberRollups:     digest.MemberRollups(rows),
		Resolutions:       []models.Resolution{},
	}
	for _, row := range rows {
		cert.Resolutions = append(cert.Resolutions, models.Resolution{
			ModID:         row.ModID,
			PolicyBasis:   row.PolicyBasis,
			ResolveSource: row.ResolveSource,
			GateAction:    row.GateAction,
		})
	}

	repro := models.ReproExport{
		ModuleBatchID: m.ModuleBatchID,
		ExportDigest:  exportDigest,
		PinDigests:    pinDigests,
	}

	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "integrity_report.json"), rows); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "integrity_certificate.json"), cert); err != nil {
		return err
	}
	return writeJSON(filepath.Join(outDir, "repro_digest_export.json"), repro)
}

func floorOK(bin, toolchain, floor string) bool {
	cmd := exec.Command(bin, toolchain, floor)
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(out)) == "match"
}

func writeJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}
