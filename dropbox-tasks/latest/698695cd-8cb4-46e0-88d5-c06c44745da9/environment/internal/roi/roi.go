package roi

import "thermalcal/internal/mask"

type Summary struct {
	UsablePixels   int
	TrimmedMeanC   float64
	RawMin         int
	RawMax         int
	MaskFraction   float64
	SaturatedCount int
}

func Summarize(
	raw []uint16,
	temps []float64,
	m *mask.Grid,
	noiseFloor int,
	saturation int,
) Summary {
	var sum float64
	var count int
	rawMin := int(^uint(0) >> 1)
	rawMax := 0
	sat := 0
	total := len(raw)
	masked := 0
	for i, v := range raw {
		if !m.Data[i] {
			masked++
			continue
		}
		if int(v) >= saturation {
			sat++
			continue
		}
		if int(v) < noiseFloor {
			continue
		}
		if int(v) < rawMin {
			rawMin = int(v)
		}
		if int(v) > rawMax {
			rawMax = int(v)
		}
		sum += temps[i]
		count++
	}
	mean := 0.0
	if count > 0 {
		mean = sum / float64(count)
	}
	if rawMin == int(^uint(0)>>1) {
		rawMin = 0
	}
	frac := 0.0
	if total > 0 {
		frac = float64(masked) / float64(total)
	}
	return Summary{
		UsablePixels:   count,
		TrimmedMeanC:   mean,
		RawMin:         rawMin,
		RawMax:         rawMax,
		MaskFraction:   frac,
		SaturatedCount: sat,
	}
}
