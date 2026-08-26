package report

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

type FrameSummary struct {
	SessionID      string  `json:"session_id"`
	FrameID        string  `json:"frame_id"`
	TimestampS     float64 `json:"timestamp_s"`
	RawMin         int     `json:"raw_min"`
	RawMax         int     `json:"raw_max"`
	UsablePixels   int     `json:"usable_pixels"`
	TrimmedMeanC   float64 `json:"trimmed_mean_c"`
	MaskFraction   float64 `json:"mask_fraction"`
	SaturatedPixels int    `json:"saturated_pixels"`
}

type SessionFit struct {
	SessionID          string  `json:"session_id"`
	AmbientTemperatureC float64 `json:"ambient_temperature_c"`
	AmplitudeC         float64 `json:"amplitude_c"`
	CoolingRateK       float64 `json:"cooling_rate_k"`
	HalfLifeS          float64 `json:"half_life_s"`
	ResidualRMSC       float64 `json:"residual_rms_c"`
}

type SessionReport struct {
	SessionID          string   `json:"session_id"`
	CameraID           string   `json:"camera_id"`
	FrameCount         int      `json:"frame_count"`
	UsableFrameCount   int      `json:"usable_frame_count"`
	StartTemperatureC  float64  `json:"start_temperature_c"`
	EndTemperatureC    float64  `json:"end_temperature_c"`
	AmbientTemperatureC float64 `json:"ambient_temperature_c"`
	CoolingRateK       float64  `json:"cooling_rate_k"`
	HalfLifeS          float64  `json:"half_life_s"`
	ResidualRMSC       float64  `json:"residual_rms_c"`
	MaxAbsResidualC    float64  `json:"max_abs_residual_c"`
	MeanUsablePixels   float64  `json:"mean_usable_pixels"`
	Flags              []string `json:"flags"`
}

type GlobalSummary struct {
	SessionCount      int     `json:"session_count"`
	TotalFrames       int     `json:"total_frames"`
	MeanResidualRMSC  float64 `json:"mean_residual_rms_c"`
}

type CalibrationReport struct {
	SchemaVersion    string          `json:"schema_version"`
	TerraformVersion string          `json:"terraform_version"`
	InputDigest      string          `json:"input_digest"`
	Sessions         []SessionReport `json:"sessions"`
	GlobalSummary    GlobalSummary   `json:"global_summary"`
}

type Writer struct {
	FrameSummaries []FrameSummary
	SessionFits    []SessionFit
	Report         CalibrationReport
}

func (w *Writer) WriteAll(outputDir string) error {
	if err := os.MkdirAll(filepath.Join(outputDir, "intermediate"), 0o755); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outputDir, "calibration_report.json"), w.Report); err != nil {
		return err
	}
	if err := writeJSONL(filepath.Join(outputDir, "intermediate/frame_summaries.jsonl"), w.FrameSummaries); err != nil {
		return err
	}
	return writeJSONL(filepath.Join(outputDir, "intermediate/session_fits.jsonl"), w.SessionFits)
}

func writeJSON(path string, v any) error {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0o644)
}

func writeJSONL(path string, rows any) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	switch rs := rows.(type) {
	case []FrameSummary:
		for _, r := range rs {
			if err := enc.Encode(r); err != nil {
				return err
			}
		}
	case []SessionFit:
		for _, r := range rs {
			if err := enc.Encode(r); err != nil {
				return err
			}
		}
	}
	return nil
}

func SortSessions(sessions []SessionReport) {
	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].SessionID < sessions[j].SessionID
	})
}
