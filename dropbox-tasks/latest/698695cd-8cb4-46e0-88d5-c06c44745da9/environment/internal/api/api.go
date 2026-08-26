package api

import (
	"path/filepath"
	"sort"

	"thermalcal/internal/checksum"
	"thermalcal/internal/config"
	"thermalcal/internal/fit"
	"thermalcal/internal/mask"
	"thermalcal/internal/pngio"
	"thermalcal/internal/radiometry"
	"thermalcal/internal/report"
	"thermalcal/internal/roi"
	"thermalcal/internal/terraform"
)

type Options struct {
	ProjectRoot string
	InputDir    string
	OutputDir   string
}

func Run(opts Options) error {
	manifestPath := filepath.Join(opts.InputDir, "manifest.json")
	manifest, err := config.LoadManifest(manifestPath)
	if err != nil {
		return err
	}
	constants, tfVersion, err := terraform.RenderConstants(opts.ProjectRoot)
	if err != nil {
		return err
	}
	digest, err := checksum.DirectoryDigest(opts.InputDir)
	if err != nil {
		return err
	}

	darkPath := config.ResolvePath(opts.InputDir, manifest.CalRefs.Dark)
	flatPath := config.ResolvePath(opts.InputDir, manifest.CalRefs.Flat)
	roiPath := config.ResolvePath(opts.InputDir, manifest.CalRefs.ROIMask)
	deadPath := config.ResolvePath(opts.InputDir, manifest.CalRefs.DeadPixelMask)

	darkImg, err := pngio.ReadGray16(darkPath)
	if err != nil {
		return err
	}
	flatImg, err := pngio.ReadGray16(flatPath)
	if err != nil {
		return err
	}
	roiImg, err := pngio.ReadGray16(roiPath)
	if err != nil {
		return err
	}
	deadImg, err := pngio.ReadGray16(deadPath)
	if err != nil {
		return err
	}

	perPixelDark := radiometry.PerPixelDark(darkImg.Data)
	flatGain := radiometry.FlatGain(flatImg.Data)
	roiMask := mask.FromGray16(roiImg.Data, roiImg.Width, roiImg.Height, 32768)
	deadMask := mask.FromGray16(deadImg.Data, deadImg.Width, deadImg.Height, 32768)
	combined := mask.Combine(roiMask, deadMask)
	activeMask := mask.Erode(combined, manifest.MaskErosionPx)

	var writer report.Writer
	writer.Report = report.CalibrationReport{
		SchemaVersion:    "1.0",
		TerraformVersion: tfVersion,
		InputDigest:      digest,
	}

	totalFrames := 0
	var residualSum float64

	for _, sess := range manifest.Sessions {
		cam, ok := constants[sess.CameraID]
		if !ok {
			continue
		}
		var times []float64
		var temps []float64
		usableFrames := 0
		var pixelSum float64

		for _, fr := range sess.Frames {
			framePath := config.ResolvePath(opts.InputDir, fr.Path)
			img, err := pngio.ReadGray16(framePath)
			if err != nil {
				return err
			}
			tempsGrid := make([]float64, len(img.Data))
			for i, raw := range img.Data {
				tempsGrid[i] = radiometry.CountsToTemperature(
					float64(raw), fr.TimestampS, perPixelDark[i], flatGain[i], cam,
				)
			}
			summary := roi.Summarize(img.Data, tempsGrid, activeMask, manifest.NoiseFloorDN, manifest.SaturationDN)
			writer.FrameSummaries = append(writer.FrameSummaries, report.FrameSummary{
				SessionID:       sess.SessionID,
				FrameID:         fr.FrameID,
				TimestampS:      fr.TimestampS,
				RawMin:          summary.RawMin,
				RawMax:          summary.RawMax,
				UsablePixels:    summary.UsablePixels,
				TrimmedMeanC:    summary.TrimmedMeanC,
				MaskFraction:    summary.MaskFraction,
				SaturatedPixels: summary.SaturatedCount,
			})
			if summary.UsablePixels > 0 {
				usableFrames++
				pixelSum += float64(summary.UsablePixels)
				times = append(times, fr.TimestampS)
				temps = append(temps, summary.TrimmedMeanC)
			}
			totalFrames++
		}

		fitRes := fit.FitCooling(times, temps)
		writer.SessionFits = append(writer.SessionFits, report.SessionFit{
			SessionID:           sess.SessionID,
			AmbientTemperatureC: fitRes.AmbientC,
			AmplitudeC:          fitRes.AmplitudeC,
			CoolingRateK:        fitRes.CoolingRateK,
			HalfLifeS:           fitRes.HalfLifeS,
			ResidualRMSC:        fitRes.ResidualRMS,
		})

		meanPixels := 0.0
		if usableFrames > 0 {
			meanPixels = pixelSum / float64(usableFrames)
		}
		writer.Report.Sessions = append(writer.Report.Sessions, report.SessionReport{
			SessionID:           sess.SessionID,
			CameraID:            sess.CameraID,
			FrameCount:          len(sess.Frames),
			UsableFrameCount:    usableFrames,
			StartTemperatureC:   fitRes.StartTempC,
			EndTemperatureC:     fitRes.EndTempC,
			AmbientTemperatureC: fitRes.AmbientC,
			CoolingRateK:        fitRes.CoolingRateK,
			HalfLifeS:           fitRes.HalfLifeS,
			ResidualRMSC:        fitRes.ResidualRMS,
			MaxAbsResidualC:     fitRes.MaxAbsResidual,
			MeanUsablePixels:    meanPixels,
			Flags:               []string{},
		})
		residualSum += fitRes.ResidualRMS
	}

	report.SortSessions(writer.Report.Sessions)
	sort.Slice(writer.FrameSummaries, func(i, j int) bool {
		a, b := writer.FrameSummaries[i], writer.FrameSummaries[j]
		if a.SessionID != b.SessionID {
			return a.SessionID < b.SessionID
		}
		if a.TimestampS != b.TimestampS {
			return a.TimestampS < b.TimestampS
		}
		return a.FrameID < b.FrameID
	})
	sort.Slice(writer.SessionFits, func(i, j int) bool {
		return writer.SessionFits[i].SessionID < writer.SessionFits[j].SessionID
	})

	writer.Report.GlobalSummary = report.GlobalSummary{
		SessionCount:     len(writer.Report.Sessions),
		TotalFrames:      totalFrames,
		MeanResidualRMSC: residualSum / float64(max(1, len(writer.Report.Sessions))),
	}

	_ = report.EnsureNested(opts.OutputDir)
	return writer.WriteAll(opts.OutputDir)
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
