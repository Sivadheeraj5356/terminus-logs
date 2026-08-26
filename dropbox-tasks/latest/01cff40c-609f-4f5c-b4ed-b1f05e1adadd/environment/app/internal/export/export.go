package export

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"

	"greenhouse-fert-gate/internal/compliance"
	"greenhouse-fert-gate/internal/profile"
	"greenhouse-fert-gate/internal/store"
)

type BatchOut struct {
	BatchID         string  `json:"batch_id"`
	ZoneID          string  `json:"zone_id"`
	DoseCount       int     `json:"dose_count"`
	ECDriftIntegral float64 `json:"ec_drift_integral"`
	ECOk            bool    `json:"ec_ok"`
	PhOk            bool    `json:"ph_ok"`
	VolumeOk        bool    `json:"volume_ok"`
	DailyVolumeOk   bool    `json:"daily_volume_ok"`
	BatchReleaseOk  bool    `json:"batch_release_ok"`
}

type SummaryOut struct {
	BatchCount    int `json:"batch_count"`
	ReleasedCount int `json:"released_count"`
}

type Report struct {
	GreenhouseID   string     `json:"greenhouse_id"`
	Batches        []BatchOut `json:"batches"`
	Summary        SummaryOut `json:"summary"`
	ComplianceHash string     `json:"compliance_hash"`
}

func ExportCompliance(st *store.Store, profilePath, outPath string) error {
	prof, err := profile.Load(profilePath)
	if err != nil {
		return err
	}
	rows, summary, err := compliance.BuildReport(st, prof)
	if err != nil {
		return err
	}
	batches := make([]BatchOut, 0, len(rows))
	for _, r := range rows {
		batches = append(batches, BatchOut{
			BatchID:         r.BatchID,
			ZoneID:          r.ZoneID,
			DoseCount:       r.DoseCount,
			ECDriftIntegral: r.ECDriftIntegral,
			ECOk:            r.ECOk,
			PhOk:            r.PhOk,
			VolumeOk:        r.VolumeOk,
			DailyVolumeOk:   r.DailyVolumeOk,
			BatchReleaseOk:  r.BatchReleaseOk,
		})
	}
	rep := Report{
		GreenhouseID: prof.GreenhouseID,
		Batches:      batches,
		Summary: SummaryOut{
			BatchCount:    summary.BatchCount,
			ReleasedCount: summary.ReleasedCount,
		},
	}
	hash, err := complianceHash(rep)
	if err != nil {
		return err
	}
	rep.ComplianceHash = hash
	raw, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(outPath, raw, 0o644)
}

func complianceHash(rep Report) (string, error) {
	payload := struct {
		GreenhouseID string     `json:"greenhouse_id"`
		Batches      []BatchOut `json:"batches"`
		Summary      SummaryOut `json:"summary"`
	}{
		GreenhouseID: rep.GreenhouseID,
		Batches:      rep.Batches,
		Summary:      rep.Summary,
	}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}
