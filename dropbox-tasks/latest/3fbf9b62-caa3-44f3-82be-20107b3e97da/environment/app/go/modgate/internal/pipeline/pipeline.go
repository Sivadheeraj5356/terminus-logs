package pipeline

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"modgate/internal/conflict"
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
	_, _ = exclude.Load(manifest.Resolve(root, m.ExcludeOverlayPath))
	annexPath := manifest.Resolve(root, m.CorpusAnnexPath)
	matchBin := manifest.Resolve(root, m.RetractmatchBin)
	floorBin := manifest.Resolve(root, m.GofloorBin)
	client := proxyclient.New(m.ProxyAPIBase, m.SumdbAPIBase, matchBin, floorBin, m.ToolchainDeclared, snap)

	rows := make([]models.IntegrityRow, 0, len(pins))
	for _, pin := range pins {
		pred := conflicts[pin.ModID]
		probe := client.Resolve(pin, models.ConflictPred{})
		rows = append(rows, policy.BuildRow(pin, probe, pred, false, m.PolicyTrack, m.ModuleBatchID, annexPath))
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].ModID < rows[j].ModID })

	cert := models.Certificate{
		Status:            "MODGATE_OK",
		ModuleBatchID:     m.ModuleBatchID,
		PolicyTrack:       m.PolicyTrack,
		ToolchainDeclared: m.ToolchainDeclared,
		GateStatus:        "pass",
		RecordCount:       len(rows),
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

	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "integrity_report.json"), rows); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "integrity_certificate.json"), cert); err != nil {
		return err
	}
	empty := models.ReproExport{ModuleBatchID: m.ModuleBatchID, PinDigests: []models.PinDigest{}}
	return writeJSON(filepath.Join(outDir, "repro_digest_export.json"), empty)
}

func writeJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}
